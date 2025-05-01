import logging
import os.path
from agr.util.image import append_images_horizontally
from redun import task, File

from agr.redun import existing_file
from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)

READ_STATS = "read_stats.jpg"
TAG_STATS = "tag_stats.jpg"
TAG_READ_STATS = "tag_read_stats.jpg"


@task()
def get_tags_reads_summary(out_dir: str, tagCountCsvs: list[File]) -> File:
    out_path = os.path.join(out_dir, "tags_reads_summary.txt")
    _ = run_catching_stderr(
        ["summarise_read_and_tag_counts", "-o", out_path]
        + [tagCountCsv.path for tagCountCsv in tagCountCsvs],
        check=True,
    )
    return File(out_path)


@task()
def get_tags_reads_list(out_dir: str, tagCountCsvs: list[File]) -> File:
    out_path = os.path.join(out_dir, "tags_reads_list.txt")
    _ = run_catching_stderr(
        [
            "summarise_read_and_tag_counts",
            "-t",
            "unsummarised",
            "-o",
            out_path,
        ]
        + [tagCountCsv.path for tagCountCsv in tagCountCsvs],
        check=True,
    )
    return File(out_path)


@task()
def get_tags_reads_cv(tags_reads_summary: File) -> File:
    out_path = os.path.join(
        os.path.dirname(tags_reads_summary.path), "tags_reads_cv.txt"
    )
    with open(out_path, "w") as out_f:
        _ = run_catching_stderr(
            ["cut", "-f", "1,4,9", tags_reads_summary.path], stdout=out_f, check=True
        )
    return File(out_path)


@task()
def get_tags_reads_plots(tags_reads_list: File) -> dict[str, File]:
    out_dir = os.path.dirname(tags_reads_list.path)
    _ = run_catching_stderr(
        [
            "tag_count_plots.R",
            f"infile={tags_reads_list.path}",
            f"outfolder={out_dir}",
        ]
    )

    # append the individual plots as was done in legacy

    def out_file(basename: str) -> File:
        return existing_file(os.path.join(out_dir, basename))

    results = {basename: out_file(basename) for basename in [READ_STATS, TAG_STATS]}

    tag_read_stats_path = os.path.join(out_dir, TAG_READ_STATS)

    append_images_horizontally(
        [results[TAG_STATS].path, results[READ_STATS].path],
        out_path=tag_read_stats_path,
    )

    return results | {TAG_READ_STATS: existing_file(tag_read_stats_path)}
