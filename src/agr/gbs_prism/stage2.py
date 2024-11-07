from functools import cached_property
import os.path
import re
from subprocess import PIPE

from agr.gquery import GQuery, Predicates

from agr.util.stdio_redirect import StdioRedirect

from .paths import GbsPaths
from .stage1 import Stage1Outputs
from .types import Cohort, flowcell_id


def _fastq_real_basename(fastq_link: str) -> str:
    return os.path.basename(os.path.realpath(fastq_link))


class Stage2Targets:
    def __init__(self, run: str, stage1: Stage1Outputs, gbs_paths: GbsPaths):
        self._run_name = run
        self._stage1 = stage1
        self._gbs_paths = gbs_paths

    def make_dirs(self):
        for cohort in self._stage1.all_cohorts:
            self._gbs_paths.make_cohort_dirs(cohort)

    def _fastq_basenames_for_cohort(self, cohort: Cohort) -> list[str]:
        return [
            _fastq_real_basename(fastq_link)
            for fastq_link in self._stage1.fastq_links(cohort)
        ]

    @property
    def all_cohort_fastq_links(self):
        return [
            os.path.join(self._gbs_paths.fastq_link_dir(cohort), fastq_basename)
            for cohort in self._stage1.all_cohorts
            for fastq_basename in self._fastq_basenames_for_cohort(cohort)
        ]

    def create_all_cohort_fastq_links(self):
        for cohort in self._stage1.all_cohorts:
            for fastq_link in self._stage1.fastq_links(cohort):
                os.symlink(
                    os.path.realpath(fastq_link),
                    os.path.join(
                        self._gbs_paths.fastq_link_dir(cohort),
                        _fastq_real_basename(fastq_link),
                    ),
                )

    def all_bwa_mapping_sampled(self, sample_moniker) -> list[str]:
        return [
            os.path.join(
                self._gbs_paths.bwa_mapping_dir(cohort),
                "%s.fastq.%s.fastq" % (fastq_basename, sample_moniker),
            )
            for cohort in self._stage1.all_cohorts
            for fastq_basename in self._fastq_basenames_for_cohort(cohort)
        ]

    def all_bwa_mapping_sampled_trimmed(self, sample_moniker) -> list[str]:
        return [
            "%s.trimmed.fastq" % sampled.removesuffix(".fastq")
            for sampled in self.all_bwa_mapping_sampled(sample_moniker)
        ]

    def _cohort_target(self, cohort: Cohort, suffix: str) -> str:
        # TODO these names are quite clunky, perhaps remove the pointless `run` prefix later
        return "%s/%s.%s.%s" % (
            self._gbs_paths.run_root,
            self._run_name,
            str(cohort),
            suffix,
        )

    @cached_property
    def all_cohort_targets(self):
        # note that some targets which were previsouly dumped into the filesystem are now simply
        # returned as lists, namely: method, bwa_references
        return [
            self._cohort_target(cohort, suffix)
            for cohort in self._stage1.all_cohorts
            for suffix in ["key", "gbsx.key", "unblind.sed"]
        ]

    def get_keyfile_for_tassel(self, cohort: Cohort, out_path: str):
        fcid = flowcell_id(self._run_name)
        with StdioRedirect(stdout=PIPE) as gbs_keyfile:
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
            ).run()
            assert gbs_keyfile.stdout is not None  # because PIPE

            # from https://github.com/AgResearch/gbs_prism/blob/dc5a71a6a2c554cd8952614d151a46ddce6892d1/ag_gbs_qc_prism.sh#L252
            enzyme_sub_re = re.compile(r"HpaIII?")  # matches HpaII or HpaIII
            enzyme_sub = "MspI"

            with open(out_path, "w") as keyfile_f:
                for line in gbs_keyfile.stdout:
                    _ = keyfile_f.write(enzyme_sub_re.sub(enzyme_sub, line))

    def get_gbsx_keyfile(self, cohort: Cohort, out_path: str):
        fcid = flowcell_id(self._run_name)
        with open(out_path, "w") as keyfile_f:
            with StdioRedirect(stdout=keyfile_f):
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
                ).run()

    def get_unblind_script(self, cohort: Cohort, out_path: str):
        fcid = flowcell_id(self._run_name)
        with open(out_path, "w") as keyfile_f:
            with StdioRedirect(stdout=keyfile_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=cohort.enzyme,
                        gbs_cohort=cohort.gbs_cohort,
                        unblinding=True,
                        columns="qc_sampleid,sample",
                        noheading=True,
                    ),
                    items=[cohort.libname],
                ).run()
