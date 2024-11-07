import logging
import subprocess

logger = logging.getLogger(__name__)


class FastqSample(object):
    def __init__(self, sample_rate: float, minimum_sample_size: int):
        self._sample_rate = sample_rate
        self._minimum_sample_size = minimum_sample_size

    @property
    def moniker(self) -> str:
        return "s%s" % ("%f" % self._sample_rate).strip("0")

    def run(self, in_path: str, out_path: str):
        err_path = "%s.err" % out_path.removesuffix(".fastq")
        with open(err_path, "w") as err_f:
            with open(out_path, "w") as out_f:
                _ = subprocess.run(
                    [
                        "seqtk",
                        "sample",
                        in_path,
                        "%f" % self._sample_rate,
                    ],
                    check=True,
                    stdout=out_f,
                    stderr=err_f,
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
                stderr=err_f,
            )
            logger.debug(
                "seqtk size %s raw output ''%s'" % (out_path, seqtk_size.stdout)
            )
            n_samples = int(seqtk_size.stdout.split()[0])
            if n_samples < self._minimum_sample_size:
                logger.debug(
                    "fastq_sample.run(%s) n_samples=%d below minimum of %d, re-sampling to minimum"
                    % (in_path, n_samples, self._minimum_sample_size)
                )
                with open(out_path, "w") as out_f:
                    _ = subprocess.run(
                        [
                            "seqtk",
                            "sample",
                            in_path,
                            "%d" % self._minimum_sample_size,
                        ],
                        check=True,
                        stdout=out_f,
                        stderr=err_f,
                    )
            else:
                logger.debug(
                    "fastq_sample.run(%s) n_samples=%d exceeds minimum of %d"
                    % (in_path, n_samples, self._minimum_sample_size)
                )
