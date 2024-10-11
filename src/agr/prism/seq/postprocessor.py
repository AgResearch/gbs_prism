import logging
import os.path
from typing import Optional

logger = logging.getLogger(__name__)


class PostProcessorError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        return "%s: %s" % (self._msg, str(self._e))


class PostProcessor(object):
    def __init__(self, postprocessing_root: str, run: str):
        self._postprocessing_root = postprocessing_root
        self._dir = os.path.join(postprocessing_root, run)

    @property
    def sample_sheet_path(self) -> str:
        return os.path.join(self._dir, "SampleSheet.csv")

    @property
    def sample_sheet_dir(self) -> str:
        return os.path.join(self._dir, "SampleSheet")

    @property
    def bclconvert_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "bclconvert")

    @property
    def fastqc_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "fastqc_run", "fastqc")

    @property
    def kmer_run_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "kmer_run")

    @property
    def kmer_fastq_sample_dir(self) -> str:
        return os.path.join(self.kmer_run_dir, "fastq_sample")

    @property
    def kmer_analysis_dir(self) -> str:
        return os.path.join(self.kmer_run_dir, "kmer_analysis")

    @property
    def dedupe_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "dedupe")

    def ensure_dirs_exist(self):
        if not os.path.isdir(self._postprocessing_root):
            raise PostProcessorError("no such directory %s" % self._postprocessing_root)
        try:
            os.makedirs(self.sample_sheet_dir, exist_ok=True)
        except Exception as e:
            raise PostProcessorError("failed to create %s" % self.sample_sheet_dir, e)
        logger.info("created %s directory" % self.sample_sheet_dir)
