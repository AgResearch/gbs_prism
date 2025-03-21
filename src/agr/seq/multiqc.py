"""This module wraps MultiQC to generate a report from FastQC and BCLConvert reports."""

import logging

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

MULTIQC_TOOL_NAME = "multiqc"


def multiqc_job_spec(
    fastqc_in_paths: list[str],
    bclconvert_top_unknowns: str,
    bclconvert_adapter_metrics: str,
    bclconvert_demultiplex_stats: str,
    bclconvert_quality_metrics: str,
    bclconvert_run_info_xml: str,
    out_dir: str,
    out_path: str,
) -> cluster.Job1Spec:
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

    return cluster.Job1Spec(
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
        expected_path=out_report,
    )
