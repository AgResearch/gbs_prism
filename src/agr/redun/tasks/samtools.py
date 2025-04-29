import os
import re
from redun import task, File

from agr.util.subprocess import run_catching_stderr
from agr.redun import one_forall

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

        map_stats = [0.0, 0.0, 0.0]  # will contain count, total, percent

        with open(stats_file.path, "r") as f:
            for record in f:
                tokens = re.split(r"\s+", record.strip())
                if len(tokens) >= 5:
                    if (tokens[3], tokens[4]) == ("in", "total"):
                        map_stats[1] = float(tokens[0])
                    elif tokens[3] == "mapped":
                        map_stats[0] = float(tokens[0])
                        if map_stats[1] > 0:
                            map_stats[2] = map_stats[0] / map_stats[1]
                        else:
                            map_stats[2] = 0.0
                        break

        stats_dict[sample_ref] = map_stats

    with open(out_path, "w") as out_f:
        print("\t".join(("sample_ref", "map_pct", "map_std")), file=out_f)
        for sample_ref in stats_dict:
            out_rec = [sample_ref, "0", "0"]
            (p, n) = (stats_dict[sample_ref][2], stats_dict[sample_ref][1])

            q = 1 - p
            stddev = 0.0
            if n > 0:
                stddev = (p * q / n) ** 0.5
            out_rec[1] = str(p * 100.0)
            out_rec[2] = str(stddev * 100.0)
            print("\t".join(out_rec), file=out_f)

    return File(out_path)
