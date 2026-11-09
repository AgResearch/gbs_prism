"""This module wraps MultiQC to generate a report from FastQC reports and custom content."""

import logging
import os.path
from redun import task, File

from redun_psij import run_job_1, Job1Spec, JobContext

logger = logging.getLogger(__name__)

MULTIQC_TOOL_NAME = "multiqc"


def _multiqc_job_spec(
    fastqc_in_paths: list[str],
    custom_content_paths: list[str],
    out_dir: str,
    out_path: str,
    job_context: JobContext,
) -> Job1Spec:
    """
    Generate a MultiQC report from FastQC reports and custom content.

    Args:
        fastqc_in_paths (list[str]): Input paths for FastQC reports.
        custom_content_paths (list[str]): Input paths for MultiQC custom content
            (`*_mqc.txt`). For MGI these carry the splitBarcode demultiplexing
            statistics, which MultiQC has no parser for - they replace the five
            bcl-convert metrics files this task used to require.
        out_dir (str): Output directory for the MultiQC report.
        out_path (str): Output path for the MultiQC report.
    """

    log_path = out_path.removesuffix(".html") + ".log"

    out_report = out_path

    return Job1Spec(
        tool=MULTIQC_TOOL_NAME,
        args=[
            "multiqc",
            "--no-clean-up",
            "--interactive",
            "--force",
            "--outdir",
            out_dir,
            "--filename",
            out_report,
        ]
        + custom_content_paths
        + fastqc_in_paths,
        stdout_path=log_path,
        stderr_path=log_path,
        custom_attributes=job_context.custom_attributes,
        expected_path=out_report,
    )


@task()
def multiqc(
    fastqc_files: list[File],
    custom_content: list[File],
    out_dir: str,
    run: str,
    job_context: JobContext,
) -> File:
    """Run MultiQC aggregating FastQC reports and demultiplexing custom content."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s_multiqc_report.html" % run)
    return run_job_1(
        _multiqc_job_spec(
            fastqc_in_paths=[fastqc_file.path for fastqc_file in fastqc_files],
            custom_content_paths=[content.path for content in custom_content],
            out_dir=out_dir,
            out_path=out_path,
            job_context=job_context,
        ),
    )
