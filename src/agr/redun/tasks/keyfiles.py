import logging
import os.path
import tempfile
from redun import task, File

from agr.gquery import GQuery, GUpdate, Predicates
from agr.seq.sequencer_run import SequencerRun
from agr.seq.types import flowcell_id, Cohort
from agr.seq.enzyme_sub import enzyme_sub_for_uneak

logger = logging.getLogger(__name__)


class GbsKeyfiles:
    def __init__(
        self,
        sequencer_run: SequencerRun,
        sample_sheet_path: str,
        root: str,
        out_dir: str,
        fastq_link_farm: str,
        backup_dir: str,
    ):
        self._sequencer_run = sequencer_run
        self._sample_sheet_path = sample_sheet_path
        self._root = root
        self._out_dir = out_dir
        self._fastq_link_farm = fastq_link_farm
        self._backup_dir = backup_dir

        self._keyfile_dump_path = os.path.join(self._backup_dir, "keyfile_dump.dat")
        self._qcsampleid_history_path = os.path.join(
            self._backup_dir, "qcsampleid_history.dat"
        )
        self._sample_sheet_dump_path = os.path.join(
            self._backup_dir, "sample_sheet_dump.dat"
        )
        self._gbs_yield_stats_dump_path = os.path.join(
            self._backup_dir, "yield_dump.dat"
        )
        self._runs_libraries_dump_path = os.path.join(
            self._backup_dir, "runs_libraries_dump.dat"
        )

    def dump_gbs_tables(self):
        # dump the GBS keyfile table
        with open(self._keyfile_dump_path, "w") as dump_f:
            GQuery(
                task="sql",
                predicates=Predicates(
                    interface_type="postgres", host="postgres_readonly"
                ),
                items=["select * from gbskeyfilefact"],
                outfile=dump_f,
            ).run()

        # dump the historical qc_sampleid (generated when a keyfile is *re*imported)
        with open(self._qcsampleid_history_path, "w") as dump_f:
            GQuery(
                task="sql",
                predicates=Predicates(
                    interface_type="postgres", host="postgres_readonly"
                ),
                items=["select * from gbs_sampleid_history_fact"],
                outfile=dump_f,
            ).run()

        # dump of the brdf table that has sample-sheet details in it
        with open(self._sample_sheet_dump_path, "w") as dump_f:
            GQuery(
                task="sql",
                predicates=Predicates(
                    interface_type="postgres", host="postgres_readonly"
                ),
                items=["select * from hiseqsamplesheetfact"],
                outfile=dump_f,
            ).run()

        # dump of the brdf table which has GBS yield stats (sample depth etc)
        with open(self._gbs_yield_stats_dump_path, "w") as dump_f:
            GQuery(
                task="sql",
                predicates=Predicates(
                    interface_type="postgres", host="postgres_readonly"
                ),
                items=["select * from gbsyieldfact"],
                outfile=dump_f,
            ).run()

        # dump of the brdf model of flowcell x library ( = biosample list x biosample)
        with open(self._runs_libraries_dump_path, "w") as dump_f:
            GQuery(
                task="sql",
                predicates=Predicates(
                    interface_type="postgres", host="postgres_readonly"
                ),
                items=[  # SQL extracted from gbs_prism/runs_libraries_dump.sql
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
                ],
                outfile=dump_f,
            ).run()

    def create(self):

        if self._sequencer_run.exists_in_database():
            logger.warning(
                "run %s already exists, continuing anyway" % self._sequencer_run.name
            )

        self.dump_gbs_tables()

        GUpdate(
            task="create_gbs_keyfiles",
            explain=True,
            predicates=Predicates(
                fastq_folder_root=self._root,
                run_folder_root=self._sequencer_run.seq_root,
                out_folder=self._out_dir,
                fastq_link_root=self._fastq_link_farm,
                sample_sheet=self._sample_sheet_path,
                import_=True,
            ),
            items=["all"],
        ).run()


@task()
def get_gbs_keyfiles(
    sequencer_run: SequencerRun,
    sample_sheet: File,
    gbs_libraries: list[str],
    deduped_fastq_files: list[File],
    root: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_dir: str,
) -> list[File]:
    """Get GBS keyfiles, which must depend on deduped fastq files having been produced."""
    _ = deduped_fastq_files  # depending on existence rather than value
    gbs_keyfiles = GbsKeyfiles(
        sequencer_run=sequencer_run,
        sample_sheet_path=sample_sheet.path,
        root=root,
        out_dir=out_dir,
        fastq_link_farm=fastq_link_farm,
        backup_dir=backup_dir,
    )
    gbs_keyfiles.create()

    return [
        File(os.path.join(out_dir, "%s.generated.txt" % library))
        for library in gbs_libraries
    ]


@task()
def get_keyfile_for_tassel(run_root_dir: str, run: str, cohort: Cohort) -> File:
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
                columns="flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link",
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
def get_keyfile_for_gbsx(run_root_dir: str, run: str, cohort: Cohort) -> File:
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
