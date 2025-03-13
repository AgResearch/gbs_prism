import logging
import subprocess

from agr.util.subprocess import run_catching_stderr
import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

FASTQ_SAMPLE_TOOL_NAME = "seqtk_sample"


class FastqSample:
    def __init__(self, sample_rate: float, minimum_sample_size: int):
        self._sample_rate = sample_rate
        self._minimum_sample_size = minimum_sample_size

    @property
    def moniker(self) -> str:
        return "s%s" % ("%f" % self._sample_rate).strip("0")

    def rate_job_spec(self, in_path: str, out_path: str) -> cluster.Job1Spec:
        """Return the primary job spec, based on sample rate."""
        return cluster.Job1Spec(
            tool=FASTQ_SAMPLE_TOOL_NAME,
            args=[
                "seqtk",
                "sample",
                in_path,
                "%f" % self._sample_rate,
            ],
            stdout_path=out_path,
            stderr_path="%s.rate.err" % out_path,
            expected_path=out_path,
        )

    def minsize_job_spec(self, in_path: str, out_path: str) -> cluster.Job1Spec:
        """Return the secondary job spec, based on minimum sample size."""
        return cluster.Job1Spec(
            tool=FASTQ_SAMPLE_TOOL_NAME,
            args=[
                "seqtk",
                "sample",
                in_path,
                "%d" % self._minimum_sample_size,
            ],
            stdout_path=out_path,
            stderr_path="%s.minsize.err" % out_path,
            expected_path=out_path,
        )

    def is_minsize_job_required(self, in_path: str, rate_sample_path: str) -> bool:
        """After running the primary job, check the sample size output to see whether a bigger resample is required."""
        seqtk_size = run_catching_stderr(
            [
                "seqtk",
                "size",
                rate_sample_path,
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        logger.debug(
            "seqtk size %s raw output ''%s'" % (rate_sample_path, seqtk_size.stdout)
        )
        n_samples = int(seqtk_size.stdout.split()[0])
        if n_samples < self._minimum_sample_size:
            logger.debug(
                "fastq_sample.run(%s) n_samples=%d below minimum of %d, need to re-sample to minimum"
                % (in_path, n_samples, self._minimum_sample_size)
            )
            return True
        else:
            logger.debug(
                "fastq_sample.run(%s) n_samples=%d exceeds minimum of %d"
                % (in_path, n_samples, self._minimum_sample_size)
            )
            return False
