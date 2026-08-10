"""Demultiplex MGI (DNBSEQ) lanes with splitBarcode.

One job per lane. splitBarcode reads the lane's single undemultiplexed fastq and
writes one `<run>_<lane>_<sample>.fq.gz` per sample, plus a `<run>_<lane>_undecoded.fq.gz`
reject bin and a `BarcodeStat.txt` summary.

The barcode geometry - the `-b` offsets and the `-B` barcode file's contents - is
resolved *before* this runs, by `agr.seq.mgi.barcodes.lane_plan` in the composing
task. That follows `mgi_prism`, which resolves everything derivable at parse time so
a mismatched sheet/run pair aborts before any Slurm job is submitted, rather than
after a 20-minute job produces a lane of `undecoded`.
"""

import logging
import os
import os.path
from dataclasses import dataclass

from redun import task, File
from redun_psij import (
    ExpectedPaths,
    FilteredGlob,
    JobContext,
    JobNSpec,
    get_tool_config,
    run_job_n,
)

logger = logging.getLogger(__name__)

SPLIT_BARCODES_TOOL_NAME = "split_barcodes"

# keys for job spec and result files
SPLIT_BARCODES_JOB_FASTQ = "fastq"
BARCODE_STAT_KEY = "barcode_stat"

BARCODE_STAT_FILENAME = "BarcodeStat.txt"

# splitBarcode's reject bin - MGI's "Undetermined". Not a sample, and on a GBS lane
# it is far larger than any of them, so it is excluded from the fastq list rather
# than being carried into FastQC and the merge.
UNDECODED = "undecoded"


@dataclass
class SplitBarcodesOutput:
    """One lane's demultiplexed output."""

    lane: str
    fastq_files: list[File]
    barcode_stat: File


def _split_barcodes_job_spec(
    lane: str,
    read_args: list[str],
    barcode_file: str,
    b_args: list[str],
    out_dir: str,
    job_context: JobContext,
) -> JobNSpec:
    tool_config = get_tool_config(SPLIT_BARCODES_TOOL_NAME)
    threads = tool_config.get("threads", 24)
    # `-m` is splitBarcode's *own* internal ceiling, not a request. Handing it the
    # whole Slurm allocation invites an OOM kill once its overhead sits on top, so
    # the config keeps it below `mem`. Same reasoning as mgi_prism's `mem_gb - 8`.
    max_mem_gb = tool_config.get("max_mem_gb", 88)

    log_path = os.path.join(os.path.dirname(out_dir), "%s.splitBarcode.log" % lane)

    return JobNSpec(
        tool=SPLIT_BARCODES_TOOL_NAME,
        args=["splitBarcode"]
        + read_args
        + ["--umi", "-B", barcode_file]
        + b_args
        + [
            "-o",
            out_dir,
            "-t",
            str(threads),
            "-m",
            str(max_mem_gb),
        ],
        stdout_path=log_path,
        stderr_path=log_path,
        custom_attributes=job_context.custom_attributes,
        # splitBarcode writes its own `log/splitBarcode_<timestamp>-HR.log` relative
        # to the working directory, which would otherwise be wherever redun was
        # launched from - i.e. the repo. Running in the lane's output directory keeps
        # that with the rest of the lane's output. Same reasoning as the old dedupe
        # task, which ran in its out_dir because clumpify dropped hs_err_pid files.
        cwd=out_dir,
        expected_paths=ExpectedPaths(
            required={
                # splitBarcode's own end-of-run summary, so requiring it is what
                # proves the lane finished rather than died partway.
                BARCODE_STAT_KEY: os.path.join(out_dir, BARCODE_STAT_FILENAME),
            }
        ),
        expected_globs={
            SPLIT_BARCODES_JOB_FASTQ: FilteredGlob(
                glob="%s/*.fq.gz" % out_dir,
                reject_re=UNDECODED,
            )
        },
    )


@task()
def split_barcodes_one(
    lane: str,
    read_args: list[str],
    barcode_file: File,
    b_args: list[str],
    out_dir: str,
    job_context: JobContext,
) -> SplitBarcodesOutput:
    """Demultiplex a single lane.

    Geometry arrives as already-resolved argv fragments rather than as a `LanePlan`,
    so the redun cache key is the arguments that actually affect the output - change
    an offset and this lane re-runs; change something cosmetic and it does not.
    """
    os.makedirs(out_dir, exist_ok=True)

    result = run_job_n(
        _split_barcodes_job_spec(
            lane=lane,
            read_args=read_args,
            barcode_file=barcode_file.path,
            b_args=b_args,
            out_dir=out_dir,
            job_context=job_context.with_sub(lane),
        )
    )

    return SplitBarcodesOutput(
        lane=lane,
        fastq_files=result.globbed_files[SPLIT_BARCODES_JOB_FASTQ],
        barcode_stat=result.expected_files[BARCODE_STAT_KEY],
    )
