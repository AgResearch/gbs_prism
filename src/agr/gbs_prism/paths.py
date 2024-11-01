import logging
import os.path
from typing import Optional

logger = logging.getLogger(__name__)


class PathsError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        return "%s: %s" % (self._msg, str(self._e))


def _makedir(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        raise PathsError("failed to create %s" % path, e)
    logger.info("created %s directory" % path)


class Paths(object):
    def __init__(self, root: str, run: str):
        self._root = root
        self._dir = os.path.join(root, run)

    @property
    def root(self) -> str:
        return self._root

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

    def makedirs(self):
        if not os.path.isdir(self._root):
            raise PathsError("no such directory %s" % self._root)
        _makedir(self.sample_sheet_dir)
        _makedir(self.bclconvert_dir)
        _makedir(self.fastqc_dir)
        _makedir(self.kmer_run_dir)
        _makedir(self.kmer_fastq_sample_dir)
        _makedir(self.kmer_analysis_dir)
        _makedir(self.dedupe_dir)
