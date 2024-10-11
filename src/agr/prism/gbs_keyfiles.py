import os.path

from agr.gquery import GQuery, GUpdate, Predicates
from agr.util import StdioRedirect

from .seq.sequencer_run import SequencerRun
from .seq.sample_sheet import SampleSheet


class GbsKeyfiles:
    def __init__(
        self,
        sequencer_run: SequencerRun,
        sample_sheet: SampleSheet,
        postprocessing_root: str,
        out_dir: str,
        fastq_link_farm: str,
        backup_dir: str,
    ):
        self._sequencer_run = sequencer_run
        self._sample_sheet = sample_sheet
        self._postprocessing_root = postprocessing_root
        self._out_dir = out_dir
        self._fastq_link_farm = fastq_link_farm
        self._backup_dir = backup_dir

        self._sample_ids = self._get_sample_ids()

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

    def _get_sample_ids(self):
        if (
            generate_keyfile_section := self._sample_sheet.get_section(
                "GenerateKeyfile"
            )
        ) is not None and (
            sample_ids := generate_keyfile_section.named_column("Sample_ID")
        ) is not None:
            return list(set(sample_ids))
        else:
            return []

    def output(self):
        return [
            os.path.join(self._out_dir, "%s.generated.txt" % sample_id)
            for sample_id in self._sample_ids
        ]

    def dump_gbs_tables(self):
        # dump the GBS keyfile table
        with open(self._keyfile_dump_path, "w") as dump_f:
            with StdioRedirect(stdout=dump_f):
                GQuery(
                    task="sql",
                    predicates=Predicates(
                        interface_type="postgres", host="postgres_readonly"
                    ),
                    items=["select * from gbskeyfilefact"],
                ).run()

        # dump the historical qc_sampleid (generated when a keyfile is *re*imported)
        with open(self._qcsampleid_history_path, "w") as dump_f:
            with StdioRedirect(stdout=dump_f):
                GQuery(
                    task="sql",
                    predicates=Predicates(
                        interface_type="postgres", host="postgres_readonly"
                    ),
                    items=["select * from gbs_sampleid_history_fact"],
                ).run()

        # dump of the brdf table that has sample-sheet details in it
        with open(self._sample_sheet_dump_path, "w") as dump_f:
            with StdioRedirect(stdout=dump_f):
                GQuery(
                    task="sql",
                    predicates=Predicates(
                        interface_type="postgres", host="postgres_readonly"
                    ),
                    items=["select * from hiseqsamplesheetfact"],
                ).run()

        # dump of the brdf table which has GBS yield stats (sample depth etc)
        with open(self._gbs_yield_stats_dump_path, "w") as dump_f:
            with StdioRedirect(stdout=dump_f):
                GQuery(
                    task="sql",
                    predicates=Predicates(
                        interface_type="postgres", host="postgres_readonly"
                    ),
                    items=["select * from gbsyieldfact"],
                ).run()

        # dump of the brdf model of flowcell x library ( = biosample list x biosample)
        with open(self._runs_libraries_dump_path, "w") as dump_f:
            with StdioRedirect(stdout=dump_f):
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
"""
                    ],
                ).run()

    def create(self):

        if self._sequencer_run.exists_in_database():
            print("not creating GBS keyfiles in database - run already exists")
            return

        self.dump_gbs_tables()

        create_gbs_keyfiles = GUpdate(
            task="create_gbs_keyfiles",
            explain=True,
            predicates=Predicates(
                fastq_folder_root=self._postprocessing_root,
                run_folder_root=self._sequencer_run.seq_root,
                out_folder=self._out_dir,
                fastq_link_root=self._fastq_link_farm,
                sample_sheet=self._sample_sheet.path,
                import_=True,
            ),
            items=["all"],
        )
        print(create_gbs_keyfiles)
        create_gbs_keyfiles.run()
