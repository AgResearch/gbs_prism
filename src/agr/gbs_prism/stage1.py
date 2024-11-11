import logging
import os.path

from agr.seq.sample_sheet import SampleSheet

from .paths import SeqPaths

logger = logging.getLogger(__name__)


class Stage1Targets:
    def __init__(self, run_name: str, sample_sheet: SampleSheet, seq_paths: SeqPaths):
        self._run_name = run_name
        self._sample_sheet = sample_sheet
        self._seq_paths = seq_paths

    @property
    def all_bclconvert_fastq_files(self) -> list[str]:
        return [
            os.path.join(self._seq_paths.bclconvert_dir, fastq_file)
            for fastq_file in self._sample_sheet.fastq_files
        ]

    @property
    def all_fastqc(self) -> list[str]:
        return [
            os.path.join(self._seq_paths.fastqc_dir, out_file)
            for fastq_file in self._sample_sheet.fastq_files
            for out_file in [
                "%s%s" % (os.path.basename(fastq_file).removesuffix(".fastq.gz"), ext)
                for ext in ["_fastqc.html", "_fastqc.zip"]
            ]
        ]

    def all_kmer_sampled(self, sample_moniker) -> list[str]:
        return [
            os.path.join(
                self._seq_paths.kmer_fastq_sample_dir,
                "%s.fastq.%s.fastq" % (fastq_file, sample_moniker),
            )
            for fastq_file in self._sample_sheet.fastq_files
        ]

    def all_kmer_analysis(self, sample_moniker, kmer_prism_moniker) -> list[str]:
        return [
            os.path.join(
                self._seq_paths.kmer_analysis_dir,
                "%s.%s.1" % (os.path.basename(kmer_sample), kmer_prism_moniker),
            )
            for kmer_sample in self.all_kmer_sampled(sample_moniker)
        ]

    @property
    def all_dedupe(self) -> list[str]:
        return [
            os.path.join(self._seq_paths.dedupe_dir, fastq_file)
            for fastq_file in self._sample_sheet.fastq_files
        ]

    def all_gbs_keyfiles(self, keyfiles_dir) -> list[str]:
        return [
            os.path.join(keyfiles_dir, "%s.generated.txt" % sample_id)
            for sample_id in self._sample_sheet.gbs_libraries
        ]


class Stage1Outputs(object):
    def __init__(self, run_name: str, fastq_link_farm: str):
        self._run_name = run_name
        self._fastq_link_farm = fastq_link_farm
