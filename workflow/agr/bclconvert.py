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
        return "%s: %s" % (self.msg, str(self.e))

class BclConvert(object):
    def __init__(self, in_dir: str, sample_sheet_path: str, out_dir: str):
        self.in_dir = in_dir
        self.sample_sheet_path = sample_sheet_path
        self.out_dir = out_dir
        if not os.path.isdir(in_dir):
            raise BclConvertError("no such directory %s" % in_dir)

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

    def ensure_dirs_exist(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except Exception as e:
            raise BclConvertError("failed to create %s" % self.out_dir, e)
        logger.info("created %s directory" % self.out_dir)

    def run(self):
        with open(self.log_path, 'a') as log_f:
            subprocess.run(["bcl-convert", "--force", "--bcl-input-directory", self.in_dir, "--sample-sheet", self.sample_sheet_path, "--output-directory", self.out_dir], check=True, stdout=log_f, stderr=log_f)

        pathlib.Path(self.fastq_complete_path).touch()
