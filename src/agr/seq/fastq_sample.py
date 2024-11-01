import logging
import os.path
import subprocess

logger = logging.getLogger(__name__)


class FastqSample(object):
    def __init__(self, out_dir: str, sample_rate: float, minimum_sample_size: int):
        self._out_dir = out_dir
        self._sample_rate = sample_rate
        self._minimum_sample_size = minimum_sample_size

    @property
    def log_path(self) -> str:
        return os.path.join(self._out_dir, "fastq_sample.log")

    def output(self, fastq_file: str) -> str:
        sample_rate_moniker = ("%f" % self._sample_rate).strip("0")
        return os.path.join(
            self._out_dir,
            "%s.fastq.s%s.fastq" % (os.path.basename(fastq_file), sample_rate_moniker),
        )

    def run(self, fastq_path: str):
        out_path = self.output(fastq_path)
        with open(self.log_path, "w") as log_f:
            with open(out_path, "w") as out_f:
                _ = subprocess.run(
                    [
                        "seqtk",
                        "sample",
                        fastq_path,
                        "%f" % self._sample_rate,
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
            if n_samples < self._minimum_sample_size:
                logger.debug(
                    "fastq_sample.run(%s) n_samples=%d below minimum of %d, re-sampling to minimum"
                    % (fastq_path, n_samples, self._minimum_sample_size)
                )
                with open(out_path, "w") as out_f:
                    _ = subprocess.run(
                        [
                            "seqtk",
                            "sample",
                            fastq_path,
                            "%d" % self._minimum_sample_size,
                        ],
                        check=True,
                        stdout=out_f,
                        stderr=log_f,
                    )
            else:
                logger.debug(
                    "fastq_sample.run(%s) n_samples=%d exceeds minimum of %d"
                    % (fastq_path, n_samples, self._minimum_sample_size)
                )
