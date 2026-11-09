import os
import re
from redun import task, File

from agr.util.subprocess import run_catching_stderr
from agr.redun import one_forall, existing_file
from agr.gbs_prism.mapping_summary import (
    indicated_mapping_rows,
    mapping_pct_and_std,
    parse_flagstat,
    write_mapping_summary,
)

import logging

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
    """run samtools flagstat for multiple files."""
    return one_forall(bam_stats_one, bam_files)


@task()
def collate_mapping_stats(stats_files: list[File], out_path: str) -> File:
    """Mapping % for every sample and reference, as `stats_summary.txt`."""
    # adapted, fixed, and simplified from legacy seq_prisms collate_mapping_stats.py

    stats_dict = {}

    for stats_file in sorted(
        stats_files,
        key=lambda file: file.path,
    ):
        sample_ref = re.sub(
            # fixed this regex to actually match our filenames 🤦
            r"(\.txt)?(\.gz)?\.fastq\.[sm]\d+\.trimmed\.fastq\.bwa",
            "",
            os.path.basename(stats_file.path),
        )
        sample_ref = re.sub(r"\.B10\.stats", "", sample_ref)

        stats_dict[sample_ref] = mapping_pct_and_std(parse_flagstat(stats_file.path))

    with open(out_path, "w") as out_f:
        print("\t".join(("sample_ref", "map_pct", "map_std")), file=out_f)
        for sample_ref, (map_pct, map_std) in stats_dict.items():
            print("\t".join((sample_ref, str(map_pct), str(map_std))), file=out_f)

    return File(out_path)


@task()
def collate_indicated_mapping_stats(
    stats_by_cohort: dict[str, list[File]],
    refs_by_cohort: dict[str, list[str]],
    indicated_by_cohort: dict[str, list[str]],
    out_path: str,
) -> File:
    """Mapping % for the keyfile-indicated reference(s) of each cohort only."""
    rows = indicated_mapping_rows(
        stats_by_cohort={
            cohort: [file.path for file in files]
            for cohort, files in stats_by_cohort.items()
        },
        refs_by_cohort=refs_by_cohort,
        indicated_by_cohort=indicated_by_cohort,
    )
    write_mapping_summary(rows, out_path)
    return File(out_path)


@task()
def plot_mapping_stats(mapping_summary: File) -> File:
    """Bar chart of the indicated mapping summary, as `mapping_stats.jpg` alongside it."""
    data_dir = os.path.dirname(mapping_summary.path)
    _ = run_catching_stderr(
        [
            "mapping_stats_plots.R",
            f"datafolder={data_dir}",
            f"summary={os.path.basename(mapping_summary.path)}",
        ],
        check=True,
    )
    return existing_file(os.path.join(data_dir, "mapping_stats.jpg"))
