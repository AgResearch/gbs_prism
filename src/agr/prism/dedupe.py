import logging
import os.path
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class DedupeError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self.msg = msg
        self.e = e

    def __str__(self) -> str:
        if self.e is None:
            return self.msg
        else:
            return "%s: %s" % (self.msg, str(self.e))


class Dedupe(object):
    def __init__(
        self,
        out_dir: str,
        tmp_dir: str,
        jvm_args: list[str] = ["-Xmx80g"],
        clumpify_args: list[str] = ["dedupe", "optical", "dupedist=15000", "subs=0"],
    ):
        self.out_dir = out_dir
        self.tmp_dir = tmp_dir
        self.jvm_args = jvm_args
        self.clumpify_args = clumpify_args

    def ensure_dirs_exist(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except Exception as e:
            raise DedupeError("failed to create %s" % self.out_dir, e)
        logger.info("created %s directory" % self.out_dir)

    def output(self, fastq_file: str) -> str:
        return os.path.join(self.out_dir, os.path.basename(fastq_file))

    def run(self, fastq_path: str):
        out_path = self.output(fastq_path)
        stdout_path = "%s.stdout" % out_path
        stderr_path = "%s.stderr" % out_path
        with open(stdout_path, "w") as stdout_f:
            with open(stderr_path, "w") as stderr_f:
                subprocess.run(
                    ["clumpify.sh"]
                    + self.jvm_args
                    + self.clumpify_args
                    + [
                        "tmpdir=%s" % self.tmp_dir,
                        "in=%s" % fastq_path,
                        "out=%s" % out_path,
                    ],
                    # $DEDUPEOPTS tmpdir=\$mytmpdir in=$file out=$OUT_ROOT/dedupe/$base  2>${OUT_ROOT}/dedupe/${base}.stderr 1>${OUT_ROOT}/dedupe/${base}.stdout
                    check=True,
                    stdout=stdout_f,
                    stderr=stderr_f,
                )
