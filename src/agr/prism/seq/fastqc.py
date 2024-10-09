import logging
import os.path
import subprocess
from typing import Optional, List

logger = logging.getLogger(__name__)


class FastqcError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self.msg = msg
        self.e = e

    def __str__(self) -> str:
        if self.e is None:
            return self.msg
        else:
            return "%s: %s" % (self.msg, str(self.e))


class Fastqc(object):
    def __init__(self, out_rootdir: str):
        self.out_dir = os.path.join(out_rootdir, "fastqc_run", "fastqc")

    @property
    def log_path(self) -> str:
        return os.path.join(self.out_dir, "fastqc.log")

    def ensure_dirs_exist(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except Exception as e:
            raise FastqcError("failed to create %s" % self.out_dir, e)
        logger.info("created %s directory" % self.out_dir)

    def output(self, fastq_file: str) -> List[str]:
        output = [
            os.path.join(self.out_dir, out_file)
            for out_file in [
                "%s%s" % (os.path.basename(fastq_file).removesuffix(".fastq.gz"), ext)
                for ext in ["_fastqc.html", "_fastqc.zip"]
            ]
        ]
        return output

    def run(self, fastq_path: str, num_threads: int = 8):
        with open(self.log_path, "w") as log_f:
            subprocess.run(
                [
                    "fastqc",
                    "-t",
                    str(num_threads),
                    "-o",
                    self.out_dir,
                    fastq_path,
                ],
                check=True,
                stdout=log_f,
                stderr=log_f,
            )
