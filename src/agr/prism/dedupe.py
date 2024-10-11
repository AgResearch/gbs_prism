import logging
import os.path
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class DedupeError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        if self._e is None:
            return self._msg
        else:
            return "%s: %s" % (self._msg, str(self._e))


class Dedupe(object):
    def __init__(
        self,
        out_dir: str,
        tmp_dir: str,
        jvm_args: list[str] = ["-Xmx80g"],
        clumpify_args: list[str] = ["dedupe", "optical", "dupedist=15000", "subs=0"],
    ):
        self._out_dir = out_dir
        self._tmp_dir = tmp_dir
        self._jvm_args = jvm_args
        self._clumpify_args = clumpify_args

    def ensure_dirs_exist(self):
        try:
            os.makedirs(self._out_dir, exist_ok=True)
        except Exception as e:
            raise DedupeError("failed to create %s" % self._out_dir, e)
        logger.info("created %s directory" % self._out_dir)

    def output(self, fastq_file: str) -> str:
        return os.path.join(self._out_dir, os.path.basename(fastq_file))

    def run(self, fastq_path: str):
        out_path = self.output(fastq_path)
        stdout_path = "%s.stdout" % out_path
        stderr_path = "%s.stderr" % out_path
        with open(stdout_path, "w") as stdout_f:
            with open(stderr_path, "w") as stderr_f:
                _ = subprocess.run(
                    ["clumpify.sh"]
                    + self._jvm_args
                    + self._clumpify_args
                    + [
                        "tmpdir=%s" % self._tmp_dir,
                        "in=%s" % fastq_path,
                        "out=%s" % out_path,
                    ],
                    check=True,
                    stdout=stdout_f,
                    stderr=stderr_f,
                )
