import logging
import os.path
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class FastqSampleError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self.msg = msg
        self.e = e

    def __str__(self) -> str:
        if self.e is None:
            return self.msg
        else:
            return "%s: %s" % (self.msg, str(self.e))


class FastqSample(object):
    def __init__(self, out_rootdir: str, sample_rate: float, minimum_sample_size: int):
        self.out_dir = os.path.join(out_rootdir, "fastq_sample")
        self.sample_rate = sample_rate
        self.minimum_sample_size = minimum_sample_size

    @property
    def log_path(self) -> str:
        return os.path.join(self.out_dir, "fastq_sample.log")

    def ensure_dirs_exist(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except Exception as e:
            raise FastqSampleError("failed to create %s" % self.out_dir, e)
        logger.info("created %s directory" % self.out_dir)

    def output(self, fastq_file: str) -> str:
        sample_rate_moniker = ("%f" % self.sample_rate).strip("0")
        return os.path.join(
            self.out_dir,
            "%s.fastq.s%s.fastq" % (os.path.basename(fastq_file), sample_rate_moniker),
        )

    def run(self, fastq_path: str):
        out_path = self.output(fastq_path)
        with open(self.log_path, "w") as log_f:
            with open(out_path, "w") as out_f:
                subprocess.run(
                    [
                        "seqtk",
                        "sample",
                        fastq_path,
                        "%f" % self.sample_rate,
                    ],
                    check=True,
                    stdout=out_f,
                    stderr=log_f,
                )
                # check sufficient output samples
            seqtk_size = subprocess.run(
                [
                    "seqtk",
                    "size",
                    out_path,
                ],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=log_f,
            )
            logger.debug(
                "seqtk size %s raw output ''%s'" % (out_path, seqtk_size.stdout)
            )
            n_samples = int(seqtk_size.stdout.split()[0])
            if n_samples < self.minimum_sample_size:
                logger.debug(
                    "fastq_sample.run(%s) n_samples=%d below minimum of %d, re-sampling to minimum"
                    % (fastq_path, n_samples, self.minimum_sample_size)
                )
                with open(out_path, "w") as out_f:
                    subprocess.run(
                        [
                            "seqtk",
                            "sample",
                            fastq_path,
                            "%d" % self.minimum_sample_size,
                        ],
                        check=True,
                        stdout=out_f,
                        stderr=log_f,
                    )
            else:
                logger.debug(
                    "fastq_sample.run(%s) n_samples=%d exceeds minimum of %d"
                    % (fastq_path, n_samples, self.minimum_sample_size)
                )
