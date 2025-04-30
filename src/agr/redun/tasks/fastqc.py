import logging
import os.path
from dataclasses import dataclass
from redun import task, File

from agr.redun.cluster_executor import run_job_n, JobNSpec, ResultFiles
from agr.redun import one_forall

logger = logging.getLogger(__name__)

FASTQC_TOOL_NAME = "fastqc"


@dataclass
class FastqcOutput:
    html: File
    zip: File


def fastqc_html_file(fastqc_output: FastqcOutput) -> File:
    return fastqc_output.html


def fastqc_zip_file(fastqc_output: FastqcOutput) -> File:
    return fastqc_output.zip


# keys for job spec
_HTML = "html"
_ZIP = "zip"


def _fastqc_job_spec(in_path: str, out_dir: str, num_threads: int = 8) -> JobNSpec:
    basename = os.path.basename(in_path).removesuffix(".gz").removesuffix(".fastq")
    log_path = os.path.join(
        out_dir,
        "%s_fastqc.log"
        % os.path.basename(in_path).removesuffix(".gz").removesuffix(".fastq"),
    )
    zip_out_path = os.path.join(out_dir, "%s%s" % (basename, "_fastqc.zip"))
    html_out_path = os.path.join(out_dir, "%s%s" % (basename, "_fastqc.html"))
    return JobNSpec(
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
        expected_paths={_HTML: html_out_path, _ZIP: zip_out_path},
    )


@task()
def _fastqc_output(result: ResultFiles) -> FastqcOutput:
    """Unwrap the lazy result expression and repackage the result files."""
    return FastqcOutput(
        html=result.expected_files[_HTML],
        zip=result.expected_files[_ZIP],
    )


@task()
def fastqc_one(fastq_file: File, out_dir: str) -> FastqcOutput:
    """Run fastqc on a single file."""
    os.makedirs(out_dir, exist_ok=True)
    return _fastqc_output(
        run_job_n(
            _fastqc_job_spec(in_path=fastq_file.path, out_dir=out_dir),
        )
    )


@task()
def fastqc_all(fastq_files: list[File], out_dir: str) -> list[FastqcOutput]:
    """Run fastqc on multiple files."""
    return one_forall(fastqc_one, fastq_files, out_dir=out_dir)
