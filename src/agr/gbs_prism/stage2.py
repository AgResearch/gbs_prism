from agr.seq.cutadapt import Cutadapt
from agr.seq.fastq_sample import FastqSample

from .paths import GbsPaths
from .stage1 import Stage1Outputs


class Stage2Targets:
    def __init__(self, stage1: Stage1Outputs, gbs_paths: GbsPaths):
        self._stage1 = stage1
        self._gbs_paths = gbs_paths
        self._bwa_mapping_fastq_sample = {
            cohort: FastqSample(
                out_dir=self._gbs_paths.bwa_mapping_dir(cohort),
                sample_rate=0.00005,
                minimum_sample_size=150000,
            )
            for cohort in stage1.all_cohorts
        }
        self._cutadapt = Cutadapt()

    def make_dirs(self):
        for cohort in self._stage1.all_cohorts:
            self._gbs_paths.make_cohort_dirs(cohort)

    @property
    def all_bwa_mapping_sampled(self):
        return [
            self._bwa_mapping_fastq_sample[cohort].output(fastq_link)
            for cohort in self._stage1.all_cohorts
            for fastq_link in self._stage1.fastq_links(cohort)
        ]

    def sample_all_fastq_links_for_bwa_mapping(self):
        for cohort in self._stage1.all_cohorts:
            for fastq_link in self._stage1.fastq_links(cohort):
                self._bwa_mapping_fastq_sample[cohort].run(fastq_link)

    @property
    def all_bwa_mapping_sampled_trimmed(self):
        return [
            self._cutadapt.output(
                out_dir=self._gbs_paths.bwa_mapping_dir(cohort),
                fastq_path=self._bwa_mapping_fastq_sample[cohort].output(fastq_link),
            )
            for cohort in self._stage1.all_cohorts
            for fastq_link in self._stage1.fastq_links(cohort)
        ]

    def trim_all_bwa_mapping_sampled(self):
        for cohort in self._stage1.all_cohorts:
            for fastq_link in self._stage1.fastq_links(cohort):
                self._cutadapt.run(
                    out_dir=self._gbs_paths.bwa_mapping_dir(cohort),
                    fastq_path=self._bwa_mapping_fastq_sample[cohort].output(
                        fastq_link
                    ),
                )
