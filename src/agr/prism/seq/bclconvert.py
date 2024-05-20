import logging
import os.path
import pathlib
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BclConvertError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self.msg = msg
        self.e = e

    def __str__(self) -> str:
        if self.e is None:
            return self.msg
        else:
            return "%s: %s" % (self.msg, str(self.e))


class BclConvert(object):
    def __init__(self, in_dir: str, sample_sheet_path: str, out_dir: str):
        self.in_dir = in_dir
        self.sample_sheet_path = sample_sheet_path
        self.out_dir = out_dir

    @property
    def top_unknown_path(self) -> str:
        return os.path.join(self.out_dir, "Reports", "Top_Unknown_Barcodes.csv")

    @property
    def fastq_complete_path(self) -> str:
        return os.path.join(self.out_dir, "Logs", "FastqComplete.txt")

    @property
    def log_path(self) -> str:
        return os.path.join(self.out_dir, "Logs", "1_run_bclconvert.log")

    @property
    def benchmark_path(self) -> str:
        return os.path.join(self.out_dir, "benchmarks", "run_bclconvert.txt")

    @property
    def fastq_files(self) -> set[str]:
        if not os.path.exists(self.fastq_complete_path):
            raise BclConvertError("attempting to get fastq_filenames before run")
        return set(
            [
                filename
                for filename in os.listdir(self.out_dir)
                if filename.endswith(".fastq.gz")
                and not filename.startswith("Undetermined")
            ]
        )

    def ensure_dirs_exist(self):
        if not os.path.isdir(self.in_dir):
            raise BclConvertError("no such directory %s" % self.in_dir)
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except Exception as e:
            raise BclConvertError("failed to create %s" % self.out_dir, e)
        logger.info("created %s directory" % self.out_dir)

    def run(self):
        with open(self.log_path, "a") as log_f:
            subprocess.run(
                # TODO remove this fast fakery:
                # [
                #     "touch",
                #     "Reports/Top_Unknown_Barcodes.csv",
                #     "SQ2334_S1_L001_R1_001.fastq.gz",
                #     "SQ2334_S1_L002_R1_001.fastq.gz",
                #     "SQ2335_S2_L001_R1_001.fastq.gz",
                #     "SQ2335_S2_L002_R1_001.fastq.gz",
                #     "SQ2336_S3_L001_R1_001.fastq.gz",
                #     "SQ2336_S3_L002_R1_001.fastq.gz",
                #     "SQ2337_S4_L001_R1_001.fastq.gz",
                #     "SQ2337_S4_L002_R1_001.fastq.gz",
                #     "SQ2338_S5_L001_R1_001.fastq.gz",
                #     "SQ2338_S5_L002_R1_001.fastq.gz",
                # ],
                # cwd=self.out_dir,  # TODO remove cwd, only needed for fast fakery
                [
                    "bcl-convert",
                    "--force",
                    "--bcl-input-directory",
                    self.in_dir,
                    "--sample-sheet",
                    self.sample_sheet_path,
                    "--output-directory",
                    self.out_dir,
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
