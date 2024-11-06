import os.path

from .paths import GbsPaths
from .stage1 import Stage1Outputs
from .types import Cohort


def _fastq_real_basename(fastq_link: str) -> str:
    return os.path.basename(os.path.realpath(fastq_link))


class Stage2Targets:
    def __init__(self, stage1: Stage1Outputs, gbs_paths: GbsPaths):
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
