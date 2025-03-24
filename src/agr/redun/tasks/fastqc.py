import logging
import os.path
from redun import task, File

from agr.redun.cluster_executor import run_job_1, Job1Spec
from agr.redun import one_forall

logger = logging.getLogger(__name__)

FASTQC_TOOL_NAME = "fastqc"


def _fastqc_job_spec(in_path: str, out_dir: str, num_threads: int = 8) -> Job1Spec:
    basename = os.path.basename(in_path).removesuffix(".gz").removesuffix(".fastq")
    log_path = os.path.join(
        out_dir,
        "%s_fastqc.log"
        % os.path.basename(in_path).removesuffix(".gz").removesuffix(".fastq"),
    )
    out_path = os.path.join(out_dir, "%s%s" % (basename, "_fastqc.zip"))
    return Job1Spec(
        tool=FASTQC_TOOL_NAME,
        args=[
            "fastqc",
            "-t",
            str(num_threads),
            "-o",
            out_dir,
            in_path,
        ],
        stdout_path=log_path,
        stderr_path=log_path,
        cwd=out_dir,
        expected_path=out_path,
    )


@task()
def fastqc_one(fastq_file: File, out_dir: str) -> File:
    """Run fastqc on a single file, returning just the zip file."""
    os.makedirs(out_dir, exist_ok=True)
    return run_job_1(
        _fastqc_job_spec(in_path=fastq_file.path, out_dir=out_dir),
    )


@task()
def fastqc_all(fastq_files: list[File], out_dir: str) -> list[File]:
    """Run fastqc on multiple files, returning just the zip files."""
    return one_forall(fastqc_one, fastq_files, out_dir=out_dir)
