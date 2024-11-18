import logging
import os.path
from typing import Literal, Optional

logger = logging.getLogger(__name__)


class PathsError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        return "%s: %s" % (self._msg, str(self._e))


def _makedir(path: str):
    if not os.path.isdir(path):
        pass
        # logger.info("creating %s directory" % path)
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        raise PathsError("failed to create %s" % path, e)


class SeqPaths:
    def __init__(self, run_root: str):
        self._run_root = run_root

    @property
    def sample_sheet_path(self) -> str:
        return os.path.join(self._run_root, "SampleSheet.csv")

    @property
    def sample_sheet_dir(self) -> str:
        return os.path.join(self._run_root, "SampleSheet")

    @property
    def bclconvert_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "bclconvert")

    @property
    def fastqc_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "fastqc_run", "fastqc")

    @property
    def kmer_fastq_sample_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "kmer_run", "fastq_sample")

    @property
    def kmer_analysis_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "kmer_run", "kmer_analysis")

    @property
    def dedupe_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "dedupe")

    def _make_run_dirs(self):
        _makedir(self.sample_sheet_dir)
        _makedir(self.bclconvert_dir)
        _makedir(self.fastqc_dir)
        _makedir(self.kmer_fastq_sample_dir)
        _makedir(self.kmer_analysis_dir)
        _makedir(self.dedupe_dir)


class GbsPaths:
    def __init__(self, run_root: str):
        self._run_root = run_root

    @property
    def run_root(self) -> str:
        return self._run_root

    def fastq_link_dir(self, cohort_name: str) -> str:
        return os.path.join(self._run_root, cohort_name, "fastq")

    def bwa_mapping_dir(self, cohort_name: str) -> str:
        return os.path.join(self._run_root, "bwa_mapping", cohort_name)

    def make_cohort_dirs(self, cohort_name: str):
        _makedir(self.bwa_mapping_dir(cohort_name))
        _makedir(self.fastq_link_dir(cohort_name))


class Paths:
    def __init__(
        self,
        postprocessing_root: str,
        run: str,
        platform: Literal["iseq", "miseq", "novaseq"] = "novaseq",
    ):
        self._illumina_platform_root = os.path.join(
            postprocessing_root, "illumina", platform
        )
        self._seq_paths = SeqPaths(
            run_root=os.path.join(self._illumina_platform_root, run)
        )

        self._gbs_root = os.path.join(postprocessing_root, "gbs")
        self._gbs_paths = GbsPaths(run_root=os.path.join(self._gbs_root, run))

    @property
    def illumina_platform_root(self) -> str:
        return self._illumina_platform_root

    @property
    def seq(self) -> SeqPaths:
        return self._seq_paths

    @property
    def gbs(self) -> GbsPaths:
        return self._gbs_paths

    def make_run_dirs(self):
        if not os.path.isdir(self._illumina_platform_root):
            raise PathsError("no such directory %s" % self._illumina_platform_root)
        self._seq_paths._make_run_dirs()

    def make_cohort_dirs(self, cohort_name: str):
        if not os.path.isdir(self._gbs_root):
            raise PathsError("no such directory %s" % self._gbs_root)
        self._gbs_paths.make_cohort_dirs(cohort_name)
