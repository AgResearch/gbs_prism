import os.path
from dataclasses import dataclass
from redun import task, File

redun_namespace = "agr.gbs_prism"

from agr.seq.types import Cohort
from agr.redun import JobContext
from agr.gbs_prism.ramify_tassel_keyfile import ramify, merge_results, merge_counts
from agr.redun.tasks import (
    get_fastq_to_tag_count,
    get_tag_count,
)
from agr.redun.tasks.tassel3 import prefix_tag_count_path


@dataclass
class ConsolidatedTagCount:
    tag_counts: list[File]
    tag_count: File

    # whether we had multiple parts and therefore merged them
    # which may affect downstream processing
    merged: bool

    # In the multi-part case we need to keep each stdout separately
    # since these are reported on in `collate_barcode_yields`, in which case
    # the key is a composite of the cohort name the basename of the part directory.
    # Otherwise it is a dict of length 1, whose key is simply the cohort name.
    stdout: dict[str, File]


@task()
def create_consolidated_tag_count(
    work_dir: str,
    cohort: Cohort,
    keyfile: File,
    job_context: JobContext,
    prefix: str = "",
) -> ConsolidatedTagCount:
    tagCounts_parts_dir = os.path.join(work_dir, "tagCounts_parts")
    tagCounts_dir = os.path.join(work_dir, "tagCounts")
    os.makedirs(tagCounts_parts_dir, exist_ok=True)

    part_dirs = ramify(keyfile=keyfile.path, output_folder=tagCounts_parts_dir)

    if len(part_dirs) > 1:
        stdout = {}
        for part_dir in part_dirs:
            fastq_to_tag_count = get_fastq_to_tag_count(
                work_dir=part_dir,
                cohort=cohort,
                keyfile=keyfile,
                job_context=job_context,
            )
            stdout["%s.%s" % (cohort.name, os.path.basename(part_dir))] = (
                fastq_to_tag_count.stdout
            )

        # merge the outputs into the top level folder
        tag_counts = [
            File(path)
            for path in merge_results(
                output_folder=tagCounts_parts_dir, merge_folder=tagCounts_dir
            )
        ]

        # merge the tag counts into a single tag count file
        tag_count_path = prefix_tag_count_path(work_dir, prefix=prefix)
        with open(tag_count_path, "w") as tag_count_f:
            merge_counts(output_folder=tagCounts_parts_dir, file=tag_count_f)

        return ConsolidatedTagCount(
            tag_counts=tag_counts,
            tag_count=File(tag_count_path),
            merged=True,
            stdout=stdout,
        )

    else:
        fastq_to_tag_count = get_fastq_to_tag_count(
            work_dir=work_dir, cohort=cohort, keyfile=keyfile, job_context=job_context
        )

        tag_count = get_tag_count(fastq_to_tag_count.stdout, prefix=prefix)

        return ConsolidatedTagCount(
            tag_counts=fastq_to_tag_count.tag_counts,
            tag_count=tag_count,
            merged=False,
            stdout={cohort.name: fastq_to_tag_count.stdout},
        )
