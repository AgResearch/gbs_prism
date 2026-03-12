import logging
import os.path
import tempfile
from typing import Optional
from redun import task, File

from agr.gquery import GQuery, GUpdate, Predicates
from agr.seq.sequencer_run import SequencerRun
from agr.seq.types import flowcell_id, Cohort
from agr.seq.enzyme_sub import enzyme_sub_for_uneak

logger = logging.getLogger(__name__)


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
   b.sampletype = 'Illumina GBS Library'
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
    sequencer_run: SequencerRun,
    sample_sheet_path: str,
    root: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_ready: list[File],
) -> File:
    """Create and import a GBS keyfile for a single library.

    The library_rows parameter (header + data rows from the GenerateKeyfile
    section for this library) serves as a cache key: redun will re-run this
    task only when the library's sample sheet metadata changes.
    """
    _ = (library_rows, backup_ready)  # cache key and dependency trigger

    GUpdate(
        task="create_gbs_keyfiles",
        explain=True,
        predicates=Predicates(
            fastq_folder_root=root,
            run_folder_root=sequencer_run.seq_root,
            out_folder=out_dir,
            fastq_link_root=fastq_link_farm,
            sample_sheet=sample_sheet_path,
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
    sequencer_run: SequencerRun,
    sample_sheet_path: str,
    root: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_ready: list[File],
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
        sequencer_run=sequencer_run,
        sample_sheet_path=sample_sheet_path,
        root=root,
        out_dir=out_dir,
        fastq_link_farm=fastq_link_farm,
        backup_ready=backup_ready,
    )


@task()
def get_gbs_keyfiles(
    sequencer_run: SequencerRun,
    sample_sheet: File,
    library_specs: dict[str, list[list[str]]],
    deduped_fastq_files: list[File],
    root: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_dir: str,
) -> dict[str, File]:
    """Orchestrate per-library keyfile creation.

    Each library is processed as a separate redun task, so only libraries
    whose metadata has changed in the GenerateKeyfile section are reimported.
    Libraries are chained sequentially to prevent database deadlocks from
    concurrent imports into gbskeyfilefact.
    """
    _ = deduped_fastq_files  # depending on existence rather than value

    backup_files = dump_gbs_tables(backup_dir)

    results = {}
    prev: Optional[File] = None
    for library_name, rows in library_specs.items():
        keyfile = _sequenced_keyfile_import(
            prev=prev,
            library_name=library_name,
            library_rows=rows,
            sequencer_run=sequencer_run,
            sample_sheet_path=sample_sheet.path,
            root=root,
            out_dir=out_dir,
            fastq_link_farm=fastq_link_farm,
            backup_ready=backup_files,
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
