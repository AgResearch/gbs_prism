import logging
import os.path
import pathlib
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


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

    @property
    def top_unknown_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Top_Unknown_Barcodes.csv")

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
        if not os.path.exists(self.fastq_complete_path):
            raise BclConvertError("attempting to get fastq_filenames before run")
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

    def run(self):
        os.makedirs(self._log_dir, exist_ok=True)
        with open(self.log_path, "w") as log_f:
            _ = subprocess.run(
                [
                    "bcl-convert",
                    "--force",
                    "--bcl-input-directory",
                    self._in_dir,
                    "--sample-sheet",
                    self._sample_sheet_path,
                    "--output-directory",
                    self._out_dir,
                ],
                check=True,
                stdout=log_f,
                stderr=log_f,
            )
        # TODO: probably eventually remove this, seems no good reason to keep the fastq complete marker file:
        pathlib.Path(self.fastq_complete_path).touch()

    def check_expected_fastq_files(self, expected: set[str]):
        actual = self.fastq_files
        if actual != expected:
            anomalies = []
            missing = expected - actual
            unexpected = actual - expected
            if any(missing):
                anomalies.append(
                    "failed to find expected fastq files: %s"
                    % ", ".join(sorted(missing))
                )
            if any(unexpected):
                anomalies.append(
                    "found unexpected fastq files: %s" % ", ".join(sorted(unexpected))
                )

            raise BclConvertError("; ".join(anomalies))
