import logging
from redun import task, File

from agr.util.subprocess import run_catching_stderr
from agr.redun import one_forall

logger = logging.getLogger(__name__)


@task()
def bam_stats_one(bam_file: File) -> File:
    """run samtools flagstat for a single file."""
    out_path = "%s.stats" % bam_file.path.removesuffix(".bam")
    with open(out_path, "w") as out_f:
        _ = run_catching_stderr(
            ["samtools", "flagstat", bam_file.path], stdout=out_f, check=True
        )
    return File(out_path)


@task()
def bam_stats_all(bam_files: list[File]) -> list[File]:
    """bwa samse for multiple files with a single reference genome."""
    return one_forall(bam_stats_one, bam_files)
