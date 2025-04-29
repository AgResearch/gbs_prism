import os.path
from dataclasses import dataclass
from redun import task, File

redun_namespace = "agr.gbs_prism"

from agr.redun.tasks import (
    get_tags_reads_summary,
    get_tags_reads_list,
    get_tags_reads_plots,
    get_tags_reads_cv,
    collate_mapping_stats,
    collate_barcode_yields,
)

from .stage2 import Stage2Output


@dataclass
class Stage3Output:
    tags_reads_summary: File
    tags_reads_list: File
    tags_reads_cv: File
    tags_reads_plots: dict[str, File]
    bam_stats_summary: File
    barcode_yield_summary: File


@task()
def run_stage3(run_root: str, stage2: Stage2Output) -> Stage3Output:
    tag_counts = sorted(
        [cohort.tag_count_unblind for cohort in stage2.cohorts.values()],
        key=lambda file: file.path,
    )

    tags_reads_summary = get_tags_reads_summary(run_root, tag_counts)
    tags_reads_list = get_tags_reads_list(run_root, tag_counts)
    tags_reads_cv = get_tags_reads_cv(tags_reads_summary)
    tags_read_plots = get_tags_reads_plots(tags_reads_list)

    bam_stats_files = sorted(
        [
            bam_stats_file
            for cohort in stage2.cohorts.values()
            for bam_stats_file in cohort.bam_stats_files
        ],
        key=lambda file: file.path,
    )

    bam_stats_summary = collate_mapping_stats(
        bam_stats_files, out_path=os.path.join(run_root, "stats_summary.txt")
    )

    fastq_to_tag_count_stdouts = {
        cohort_name: cohort.fastq_to_tag_count_stdout
        for cohort_name, cohort in stage2.cohorts.items()
    }

    barcode_yield_summary = collate_barcode_yields(
        fastq_to_tag_count_stdouts,
        out_path=os.path.join(run_root, "barcode_yield_summary.txt"),
    )

    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return Stage3Output(
        tags_reads_summary=tags_reads_summary,
        tags_reads_list=tags_reads_list,
        tags_reads_cv=tags_reads_cv,
        tags_reads_plots=tags_read_plots,
        bam_stats_summary=bam_stats_summary,
        barcode_yield_summary=barcode_yield_summary,
    )
