import logging
import os.path
import tempfile
from typing import Optional
from redun import task, File

from agr.gquery import GQuery, GUpdate, Predicates
from agr.seq.types import flowcell_id, Cohort
from agr.seq.enzyme_sub import enzyme_sub_for_uneak

logger = logging.getLogger(__name__)


# Both sample types, deliberately. `realise_run_in_gbs_database` only inserts a
# biosampleob row when none exists and its check ignores sampletype, so an MGI
# library with prior Illumina history keeps its `Illumina GBS Library` row while a
# first-time library gets `MGI GBS Library`. One MGI run can contain both; filtering
# on either alone would silently back up some libraries and miss others.
_GBS_TABLE_DUMPS = [
    ("keyfile_dump.dat", "select * from gbskeyfilefact"),
    ("qcsampleid_history.dat", "select * from gbs_sampleid_history_fact"),
    ("sample_sheet_dump.dat", "select * from hiseqsamplesheetfact"),
    ("yield_dump.dat", "select * from gbsyieldfact"),
    (
        "runs_libraries_dump.dat",
        """select
   b.obid as sampleobid,
   b.samplename,
   l.obid as listobid,
   l.listname
from
   biosampleob as b join biosamplelistmembershiplink as m on
   m.biosampleob = b.obid join
   biosamplelist as l on l.obid = m.biosamplelist
where
   b.sampletype in ('Illumina GBS Library', 'MGI GBS Library')
""",
    ),
]


@task()
def dump_gbs_tables(backup_dir: str) -> list[File]:
    """Dump GBS database tables for backup. Runs once per pipeline invocation."""
    os.makedirs(backup_dir, exist_ok=True)
    dump_files = []
    for filename, sql in _GBS_TABLE_DUMPS:
        dump_path = os.path.join(backup_dir, filename)
        with open(dump_path, "w") as dump_f:
            GQuery(
                task="sql",
                predicates=Predicates(
                    interface_type="postgres", host="postgres_readonly"
                ),
                items=[sql],
                outfile=dump_f,
            ).run()
        dump_files.append(File(dump_path))
    return dump_files


@task()
def create_gbs_keyfile_for_library(
    library_name: str,
    library_rows: list[list[str]],
    sample_sheet_path: str,
    merged_fastq_dir: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_ready: list[File],
    merged_fastq: list[File] = [],
) -> File:
    """Create and import a GBS keyfile for a single library.

    The library_rows parameter (header + data rows from the GenerateKeyfile
    section for this library) serves as a cache key: redun will re-run this
    task only when the library's sample sheet metadata changes.
    The merged_fastq parameter triggers reimport when upstream fastq content
    changes.
    """
    _ = (library_rows, backup_ready, merged_fastq)  # cache key and dependency trigger

    GUpdate(
        task="create_gbs_keyfiles",
        explain=True,
        predicates=Predicates(
            # Selects gquery's Mgi class via sequencing.factory.for_platform, which
            # otherwise defaults to Illumina.
            platform="mgi",
            # MGI sheets live outside the run tree, so the path is passed rather than
            # derived. This also makes run_folder_root and fastq_folder_root dead for
            # this call, which is why neither is passed.
            sample_sheet=sample_sheet_path,
            out_folder=out_dir,
            # NB `fastq_root`, not `fastq_folder_root` - two similarly named
            # predicates for near-identical concepts, and a real footgun. Without
            # this, gquery composes Illumina's bcl2fastq layout,
            # `<fastq_folder_root>/<run>/SampleSheet/dedupe/`, which does not exist
            # for MGI. It must be the *per library* merged directory: gquery's glob
            # is prefix-anchored, so a shared directory would let SQ5420 match a
            # neighbouring SQ54201.
            fastq_root=merged_fastq_dir,
            fastq_link_root=fastq_link_farm,
            import_=True,
        ),
        items=[library_name],
    ).run()

    for suffix in [".generated.txt", ".txt"]:
        path = os.path.join(out_dir, "%s%s" % (library_name, suffix))
        if os.path.exists(path):
            return File(path)
    raise FileNotFoundError(
        "Keyfile for library %s not found in %s." % (library_name, out_dir)
    )


@task(cache=False)
def _sequenced_keyfile_import(
    prev: Optional[File],
    library_name: str,
    library_rows: list[list[str]],
    sample_sheet_path: str,
    merged_fastq_dir: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_ready: list[File],
    merged_fastq: list[File] = [],
) -> File:
    """Wrapper that serialises per-library keyfile imports.

    This task is uncached so redun always evaluates it, but the inner
    create_gbs_keyfile_for_library task *is* cached: if a library's
    inputs haven't changed it returns from cache without calling GUpdate.
    The `prev` parameter creates a chain dependency that prevents concurrent
    database imports (which cause ShareLock deadlocks on gbskeyfilefact).
    """
    _ = prev  # ordering dependency only
    return create_gbs_keyfile_for_library(
        library_name=library_name,
        library_rows=library_rows,
        sample_sheet_path=sample_sheet_path,
        merged_fastq_dir=merged_fastq_dir,
        out_dir=out_dir,
        fastq_link_farm=fastq_link_farm,
        backup_ready=backup_ready,
        merged_fastq=merged_fastq,
    )


@task()
def get_gbs_keyfiles(
    sample_sheet_path: str,
    library_specs: dict[str, list[list[str]]],
    merged_fastq: dict[str, File],
    merged_fastq_dirs: dict[str, str],
    out_dir: str,
    fastq_link_farm: str,
    backup_dir: str,
) -> dict[str, File]:
    """Orchestrate per-library keyfile creation.

    Each library is processed as a separate redun task, so only libraries
    whose metadata has changed in the GenerateKeyfile section are reimported.
    Libraries are chained sequentially to prevent database deadlocks from
    concurrent imports into gbskeyfilefact.

    `merged_fastq_dirs` is per library because gquery's fastq discovery is a flat
    listdir with a prefix-anchored match - see create_gbs_keyfile_for_library.
    """
    backup_files = dump_gbs_tables(backup_dir)

    results = {}
    prev: Optional[File] = None
    for library_name, rows in library_specs.items():
        keyfile = _sequenced_keyfile_import(
            prev=prev,
            library_name=library_name,
            library_rows=rows,
            sample_sheet_path=sample_sheet_path,
            merged_fastq_dir=merged_fastq_dirs[library_name],
            out_dir=out_dir,
            fastq_link_farm=fastq_link_farm,
            backup_ready=backup_files,
            merged_fastq=[merged_fastq[library_name]],
        )
        results[library_name] = keyfile
        prev = keyfile
    return results


@task()
def get_keyfile_for_tassel(
    run_root_dir: str, run: str, cohort: Cohort, gbs_keyfile: File
) -> File:
    _ = gbs_keyfile  # using the keyfile as a trigger for rerun
    out_path = os.path.join(run_root_dir, "%s.%s.key" % (run, cohort.name))
    fcid = flowcell_id(run)
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        GQuery(
            task="gbs_keyfile",
            badge_type="library",
            predicates=Predicates(
                flowcell=fcid,
                enzyme=cohort.enzyme,
                gbs_cohort=cohort.gbs_cohort,
                columns="flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,taxid,numberofbarcodes,windowsize,control,fastq_link,qc_cohort,gbs_cohort,sequencing_platform,geno_method,fullsamplename,factid,createddate,calibration_hint,animalid,stud,uidtag,breed,species,sample_type,genophyle_species,sample as sampleid",
            ),
            items=[cohort.libname],
            outfile=tmp_f,
        ).run()

        _ = tmp_f.seek(0)
        with open(out_path, "w") as out_f:
            for line in tmp_f:
                _ = out_f.write(enzyme_sub_for_uneak(line))
    return File(out_path)


@task()
def get_keyfile_for_gbsx(
    run_root_dir: str, run: str, cohort: Cohort, gbs_keyfile: File
) -> File:
    _ = gbs_keyfile  # using the keyfile as a trigger for rerun
    out_path = os.path.join(run_root_dir, "%s.%s.gbsx.key" % (run, cohort.name))
    fcid = flowcell_id(run)
    with open(out_path, "w") as out_f:
        GQuery(
            task="gbs_keyfile",
            badge_type="library",
            predicates=Predicates(
                flowcell=fcid,
                enzyme=cohort.enzyme,
                gbs_cohort=cohort.gbs_cohort,
                columns="qc_sampleid as sample,Barcode,Enzyme",
            ),
            items=[cohort.libname],
            outfile=out_f,
        ).run()
    return File(out_path)
