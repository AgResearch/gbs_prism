import logging
import os.path
import subprocess
from redun import task, File

from agr.util.subprocess import run_catching_stderr
from agr.redun.cluster_executor import run_job_1, Job1Spec
from agr.redun import one_forall, JobContext

logger = logging.getLogger(__name__)

FASTQ_SAMPLE_TOOL_NAME = "seqtk_sample"


class FastqSampleSpec:
    def __init__(self, rate: float, minimum_sample_size: int):
        self._rate = rate
        self._minimum_sample_size = minimum_sample_size

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def minimum_sample_size(self) -> int:
        return self._minimum_sample_size

    @property
    def rate_moniker(self) -> str:
        return "s%s" % ("%f" % self._rate).strip("0")

    @property
    def minsize_moniker(self) -> str:
        return "m%d" % self._minimum_sample_size


def _rate_job_spec(
    in_path: str, spec: FastqSampleSpec, out_path: str, job_context: JobContext
) -> Job1Spec:
    """Return the primary job spec, based on sample rate."""
    return Job1Spec(
        tool=FASTQ_SAMPLE_TOOL_NAME,
        args=[
            "seqtk",
            "sample",
            "-2",
            in_path,
            "%f" % spec._rate,
        ],
        stdout_path=out_path,
        stderr_path="%s.rate.err" % out_path,
        custom_attributes=job_context.custom_attributes,
        expected_path=out_path,
    )


def _minsize_job_spec(
    in_path: str, spec: FastqSampleSpec, out_path: str, job_context: JobContext
) -> Job1Spec:
    """Return the secondary job spec, based on minimum sample size."""
    return Job1Spec(
        tool=FASTQ_SAMPLE_TOOL_NAME,
        args=[
            "seqtk",
            "sample",
            "-2",
            in_path,
            "%d" % spec.minimum_sample_size,
        ],
        stdout_path=out_path,
        stderr_path="%s.minsize.err" % out_path,
        custom_attributes=job_context.custom_attributes,
        expected_path=out_path,
    )


def _is_minsize_job_required(
    in_path: str, spec: FastqSampleSpec, rate_sample_path: str
) -> bool:
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
    if n_samples < spec.minimum_sample_size:
        logger.debug(
            "fastq_sample.run(%s) n_samples=%d below minimum of %d, need to re-sample to minimum"
            % (in_path, n_samples, spec.minimum_sample_size)
        )
        return True
    else:
        logger.debug(
            "fastq_sample.run(%s) n_samples=%d exceeds minimum of %d"
            % (in_path, n_samples, spec.minimum_sample_size)
        )
        return False


@task()
def _sample_minsize_if_required(
    fastq_file: File,
    spec: FastqSampleSpec,
    rate_sample: File,
    out_path: str,
    job_context: JobContext,
) -> File:
    if _is_minsize_job_required(
        in_path=fastq_file.path, spec=spec, rate_sample_path=rate_sample.path
    ):
        return run_job_1(
            _minsize_job_spec(
                in_path=fastq_file.path,
                spec=spec,
                out_path=out_path,
                job_context=job_context,
            ),
        )
    else:
        return rate_sample


@task()
def fastq_sample_one(
    fastq_file: File,
    spec: FastqSampleSpec,
    out_dir: str,
    job_context: JobContext,
) -> File:
    """Sample a single fastq file according to the spec."""
    os.makedirs(out_dir, exist_ok=True)
    # the ugly name is copied from legacy gbs_prism
    basename = os.path.basename(fastq_file.path)
    rate_out_path = os.path.join(
        out_dir,
        "%s.fastq.%s.fastq" % (basename, spec.rate_moniker),
    )
    minsize_out_path = os.path.join(
        out_dir,
        "%s.fastq.%s.fastq" % (basename, spec.minsize_moniker),
    )

    rate_sample = run_job_1(
        _rate_job_spec(
            in_path=fastq_file.path,
            spec=spec,
            out_path=rate_out_path,
            job_context=job_context,
        ),
    )
    return _sample_minsize_if_required(
        fastq_file=fastq_file,
        spec=spec,
        rate_sample=rate_sample,
        out_path=minsize_out_path,
        job_context=job_context,
    )


@task()
def fastq_sample_all(
    fastq_files: list[File],
    spec: FastqSampleSpec,
    out_dir: str,
    job_context: JobContext,
) -> list[File]:
    """Sample all fastq files as required for fastq analysis."""
    return one_forall(
        fastq_sample_one,
        fastq_files,
        spec=spec,
        out_dir=out_dir,
        job_context=job_context,
    )
