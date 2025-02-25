import logging
import os.path
from typing import Optional

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

BCLCONVERT_TOOL_NAME = "bcl_convert"

# key for job spec and result files
BCLCONVERT_JOB_FASTQ = "fastq"


class BclConvertError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        if self._e is None:
            return self._msg
        else:
            return "%s: %s" % (self._msg, str(self._e))


class BclConvert:
    def __init__(self, in_dir: str, sample_sheet_path: str, out_dir: str):
        self._in_dir = in_dir
        self._sample_sheet_path = sample_sheet_path
        self._out_dir = out_dir
        self._log_dir = os.path.join(self._out_dir, "Logs")
        os.makedirs(self._log_dir, exist_ok=True)

    @property
    def top_unknown_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Top_Unknown_Barcodes.csv")

    @property
    def adapter_metrics_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Adapter_Metrics.csv")

    @property
    def demultiplex_stats_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Demultiplex_Stats.csv")

    @property
    def quality_metrics_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Quality_Metrics.csv")

    @property
    def run_info_xml_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "RunInfo.xml")

    @property
    def fastq_complete_path(self) -> str:
        return os.path.join(self._log_dir, "FastqComplete.txt")

    @property
    def log_path(self) -> str:
        return os.path.join(self._log_dir, "1_run_bclconvert.log")

    @property
    def benchmark_path(self) -> str:
        return os.path.join(self._out_dir, "benchmarks", "run_bclconvert.txt")

    @property
    def fastq_files(self) -> set[str]:
        return set(
            [
                filename
                for filename in os.listdir(self._out_dir)
                if filename.endswith(".fastq.gz")
                and not filename.startswith("Undetermined")
            ]
        )

    def fastq_path(self, fastq_file: str):
        return os.path.join(self._out_dir, fastq_file)

    @property
    def job_spec(self) -> cluster.JobNSpec:
        return cluster.JobNSpec(
            tool=BCLCONVERT_TOOL_NAME,
            args=[
                "bcl-convert",
                "--force",
                "--bcl-input-directory",
                self._in_dir,
                "--sample-sheet",
                self._sample_sheet_path,
                "--output-directory",
                self._out_dir,
            ],
            stdout_path=self.log_path,
            stderr_path=self.log_path,
            expected_paths={},
            expected_globs={
                BCLCONVERT_JOB_FASTQ: cluster.FilteredGlob(
                    glob=f"{self._out_dir}/*.fastq.gz",
                    reject_re="/Undetermined",
                )
            },
        )
