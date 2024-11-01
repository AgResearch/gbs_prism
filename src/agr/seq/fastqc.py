import logging
import os.path
import subprocess
from typing import List

logger = logging.getLogger(__name__)


class Fastqc(object):
    def __init__(self, out_dir: str):
        self._out_dir = out_dir

    @property
    def log_path(self) -> str:
        return os.path.join(self._out_dir, "fastqc.log")

    def output(self, fastq_file: str) -> List[str]:
        output = [
            os.path.join(self._out_dir, out_file)
            for out_file in [
                "%s%s" % (os.path.basename(fastq_file).removesuffix(".fastq.gz"), ext)
                for ext in ["_fastqc.html", "_fastqc.zip"]
            ]
        ]
        return output

    def run(self, fastq_path: str, num_threads: int = 8):
        with open(self.log_path, "w") as log_f:
            _ = subprocess.run(
                [
                    "fastqc",
                    "-t",
                    str(num_threads),
                    "-o",
                    self._out_dir,
                    fastq_path,
                ],
                check=True,
                stdout=log_f,
                stderr=log_f,
            )
