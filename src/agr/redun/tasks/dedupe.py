import glob
import logging
import os
import os.path
from redun import task, File

from redun_psij import get_tool_config, run_job_1, Job1Spec, JobContext
from agr.redun import one_forall
from agr.util.path import baseroot

logger = logging.getLogger(__name__)


def _base_path(out_path: str) -> str:
    return out_path.removesuffix(".gz").removesuffix(".fastq")


DEDUPE_TOOL_NAME = "dedupe"


def _dedupe_job_spec(
    in_path: str,
    out_path: str,
    tmp_dir: str,
    job_context: JobContext,
    jvm_args: list[str] = [],
    clumpify_args: list[str] = ["dedupe", "optical", "dupedist=15000", "subs=0"],
) -> Job1Spec:
    # we run in the out_dir because clumpify is in the habit of dumping hs_err_pid1234.log files.
    out_dir = os.path.dirname(out_path)
    base_path = _base_path(out_path)
    log_path = f"{base_path}.clumpfy.log"
    return Job1Spec(
        tool=DEDUPE_TOOL_NAME,
        args=["clumpify.sh"]
        + jvm_args
        + clumpify_args
        + [
            "tmpdir=%s" % tmp_dir,
            "in=%s" % in_path,
            "out=%s" % out_path,
        ],
        stdout_path=log_path,
        stderr_path=log_path,
        custom_attributes=job_context.custom_attributes,
        cwd=out_dir,
        expected_path=out_path,
    )


def _remove_dedupe_turds(out_path: str):
    # remove any turds dropped by clumpify, because these break keyfile_table_import
    # filenames are like SQ5051_S1_L001_R1_001_clumpify_p1_temp0_20b4208f2aae2ca8.fastq.gz
    base_path = _base_path(out_path)
    for turd in glob.glob(f"{base_path}_clumpify_*"):
        try:
            os.remove(turd)
        except FileNotFoundError:
            pass


@task()
def dedupe_one(fastq_file: File, out_dir: str, job_context: JobContext) -> File:
    """Dedupe a single fastq file."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(fastq_file.path))

    tool_config = get_tool_config(DEDUPE_TOOL_NAME)
    java_max_heap = tool_config.get("java_max_heap")

    result = run_job_1(
        _dedupe_job_spec(
            in_path=fastq_file.path,
            out_path=out_path,
            job_context=job_context.with_sub(baseroot(fastq_file.path)),
            tmp_dir="/tmp",  # TODO maybe need tmp_dir on large scratch partition
            jvm_args=[f"-Xmx{java_max_heap}"] if java_max_heap is not None else [],
        ),
    )
    _remove_dedupe_turds(out_path)
    return result


@task()
def dedupe_all(
    fastq_files: list[File], out_dir: str, job_context: JobContext
) -> list[File]:
    """Dedupe multiple fastq files."""
    return one_forall(dedupe_one, fastq_files, out_dir=out_dir, job_context=job_context)
