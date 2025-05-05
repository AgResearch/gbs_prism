import logging
import os.path
from dataclasses import dataclass
from redun import task, File
from typing import Optional

from agr.redun.cluster_executor import run_job_n, JobNSpec, FilteredGlob

logger = logging.getLogger(__name__)

BCLCONVERT_TOOL_NAME = "bcl_convert"

# key for job spec and result files
BCLCONVERT_JOB_FASTQ = "fastq"


class BclConvertError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        if self._e is None:
            return self._msg
        else:
            return "%s: %s" % (self._msg, str(self._e))


class BclConvertPaths:
    def __init__(self, out_dir: str):
        self._out_dir = out_dir
        self._log_dir = os.path.join(self._out_dir, "Logs")

    @property
    def top_unknown_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Top_Unknown_Barcodes.csv")

    @property
    def adapter_metrics_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Adapter_Metrics.csv")

    @property
    def demultiplex_stats_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Demultiplex_Stats.csv")

    @property
    def quality_metrics_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "Quality_Metrics.csv")

    @property
    def run_info_xml_path(self) -> str:
        return os.path.join(self._out_dir, "Reports", "RunInfo.xml")


def _bcl_convert_job_spec(
    in_dir: str,
    sample_sheet_path: str,
    out_dir: str,
) -> JobNSpec:

    # Create out and error files as *siblings* of out_dir,
    # since the out_dir itself must be created by bcl-convert,
    # and therefore doesn't exist early enough for these.
    out_path = "%s.stdout" % out_dir
    err_path = "%s.stderr" % out_dir

    return JobNSpec(
        tool=BCLCONVERT_TOOL_NAME,
        args=[
            "bcl-convert",
            "--bcl-input-directory",
            in_dir,
            "--sample-sheet",
            sample_sheet_path,
            "--output-directory",
            out_dir,
        ],
        stdout_path=out_path,
        stderr_path=err_path,
        expected_globs={
            BCLCONVERT_JOB_FASTQ: FilteredGlob(
                glob=f"{out_dir}/*.fastq.gz",
                reject_re="/Undetermined",
            )
        },
    )


@dataclass
class BclConvertOutput:
    """Dataclass to collect the outputs of bclconvert."""

    fastq_files: list[File]
    adapter_metrics: File
    demultiplexing_metrics: File
    quality_metrics: File
    run_info_xml: File
    top_unknown: File


@task()
def bcl_convert(
    in_dir: str,
    out_dir: str,
    sample_sheet_path: str,
    expected_fastq: set[str],
) -> BclConvertOutput:
    paths = BclConvertPaths(out_dir)

    fastq_files = run_job_n(
        _bcl_convert_job_spec(
            in_dir=in_dir, sample_sheet_path=sample_sheet_path, out_dir=out_dir
        )
    ).globbed_files[BCLCONVERT_JOB_FASTQ]

    return BclConvertOutput(
        fastq_files=_check_bcl_convert(fastq_files, expected_fastq),
        adapter_metrics=File(paths.adapter_metrics_path),
        demultiplexing_metrics=File(paths.demultiplex_stats_path),
        quality_metrics=File(paths.quality_metrics_path),
        run_info_xml=File(paths.run_info_xml_path),
        top_unknown=File(paths.top_unknown_path),
    )


def _check_bcl_convert(fastq_files: list[File], expected: set[str]) -> list[File]:
    """Check what we got is what we expected."""
    actual = {fastq_file.basename() for fastq_file in fastq_files}
    if actual != expected:
        anomalies = []
        missing = expected - actual
        unexpected = actual - expected
        if any(missing):
            anomalies.append(
                "failed to find expected fastq files: %s" % ", ".join(sorted(missing))
            )
        if any(unexpected):
            anomalies.append(
                "found unexpected fastq files: %s" % ", ".join(sorted(unexpected))
            )

        raise BclConvertError("; ".join(anomalies))
    return fastq_files
