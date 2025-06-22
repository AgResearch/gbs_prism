"""This module wraps MultiQC to generate a report from FastQC and BCLConvert reports."""

import logging
import os.path
from redun import task, File

from agr.redun.cluster_executor import run_job_1, Job1Spec
from agr.redun import JobContext

logger = logging.getLogger(__name__)

MULTIQC_TOOL_NAME = "multiqc"


def _multiqc_job_spec(
    fastqc_in_paths: list[str],
    bclconvert_top_unknowns: str,
    bclconvert_adapter_metrics: str,
    bclconvert_demultiplex_stats: str,
    bclconvert_quality_metrics: str,
    bclconvert_run_info_xml: str,
    out_dir: str,
    out_path: str,
    job_context: JobContext,
) -> Job1Spec:
    """
    Generate a MultiQC report from FastQC and BCLConvert reports.

    Args:
        fastqc_in_paths (list[str]): List of input paths for FastQC reports.
        bclconvert_top_unknowns (str): Path to BCLConvert top unknowns report.
        bclconvert_adapter_metrics (str): Path to BCLConvert adapter metrics report.
        bclconvert_demultiplex_stats (str): Path to BCLConvert demultiplex stats report.
        bclconvert_quality_metrics (str): Path to BCLConvert quality metrics report.
        bclconvert_run_info_xml (str): Path to BCLConvert run info XML.
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
            bclconvert_top_unknowns,
            bclconvert_adapter_metrics,
            bclconvert_demultiplex_stats,
            bclconvert_quality_metrics,
            bclconvert_run_info_xml,
        ]
        + fastqc_in_paths,
        stdout_path=log_path,
        stderr_path=log_path,
        custom_attributes=job_context.custom_attributes,
        expected_path=out_report,
    )


@task()
def multiqc(
    fastqc_files: list[File],
    bclconvert_top_unknowns: File,
    bclconvert_adapter_metrics: File,
    bclconvert_demultiplex_stats: File,
    bclconvert_quality_metrics: File,
    bclconvert_run_info_xml: File,
    out_dir: str,
    run: str,
    job_context: JobContext,
) -> File:
    """Run MultiQC aggregating FastQC and BCLConvert reports."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s_multiqc_report.html" % run)
    return run_job_1(
        _multiqc_job_spec(
            fastqc_in_paths=[fastqc_file.path for fastqc_file in fastqc_files],
            bclconvert_top_unknowns=bclconvert_top_unknowns.path,
            bclconvert_adapter_metrics=bclconvert_adapter_metrics.path,
            bclconvert_demultiplex_stats=bclconvert_demultiplex_stats.path,
            bclconvert_quality_metrics=bclconvert_quality_metrics.path,
            bclconvert_run_info_xml=bclconvert_run_info_xml.path,
            out_dir=out_dir,
            out_path=out_path,
            job_context=job_context,
        ),
    )
