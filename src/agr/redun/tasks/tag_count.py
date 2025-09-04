import os
import os.path
from dataclasses import dataclass
from redun import task, File

from agr.util.path import symlink, symlink_rel, prefixed
from agr.redun import JobContext
from agr.gbs_prism.ramify_tassel_keyfile import ramify, merge_results, merge_counts
from agr.redun.tasks.tassel3 import (
    get_fastq_to_tag_count,
    get_tag_count,
    prefix_tag_count_path,
)


@dataclass
class ConsolidatedTagCount:
    tag_counts: list[File]
    tag_count: File

    # In the multi-part case we need to keep each stdout separately
    # since these are reported on in `collate_barcode_yields`, in which case
    # the key is a composite of the cohort name the basename of the part directory.
    # Otherwise it is a dict of length 1, whose key is simply the cohort name.
    stdout: dict[str, File]


def _create_merged_directory_tree(
    work_dir: str,
    part_dirs: list[str],
    merge_folder: str,
):
    # create expected directory structure in the merge folder,
    # which is done by get_fastq_to_tag_count in the single part case

    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(merge_folder, exist_ok=True)

    # Illumina directory containing all the fastq files
    illumina_dir = os.path.join(work_dir, "Illumina")
    os.makedirs(illumina_dir, exist_ok=True)
    for part_dir in part_dirs:
        illumina_part_dir = os.path.join(part_dir, "Illumina")
        for fastq_link in os.listdir(illumina_part_dir):
            fastq_target = os.path.join(illumina_dir, fastq_link)
            fastq_source = os.readlink(os.path.join(illumina_part_dir, fastq_link))
            symlink(fastq_source, fastq_target, force=True)


@task()
def _merge_results_and_counts(
    work_dir: str,
    parts_dir: str,
    part_dirs: list[str],
    merge_folder: str,
    stdout: dict[str, File],
    tag_counts_list: list[list[File]],
    prefix: str,
) -> ConsolidatedTagCount:
    # This needs to be a task since it depends on the get_fastq_to_tag_count task.
    # However, the interface to merge_results() and merge_counts() in the legacy ramify code
    # is a bit grotty, as that code still rummages through the filesystem rather than process
    # argument list of files.

    # pretend we're using the tag_counts 😭
    _ = tag_counts_list

    _create_merged_directory_tree(
        work_dir=work_dir,
        part_dirs=part_dirs,
        merge_folder=merge_folder,
    )

    # merge the outputs into the top level folder
    tag_counts = [
        File(path)
        for path in merge_results(output_folder=parts_dir, merge_folder=merge_folder)
    ]

    # merge the tag counts into a single tag count file
    tag_count_path = prefix_tag_count_path(parts_dir, prefix=prefix)
    with open(tag_count_path, "w") as tag_count_f:
        merge_counts(output_folder=parts_dir, file=tag_count_f)

    return ConsolidatedTagCount(
        tag_counts=tag_counts,
        tag_count=File(tag_count_path),
        stdout=stdout,
    )


# work out what input files Tassel will actually use so we can make redun aware of them
def illumina_fastq_files(work_dir: str) -> list[File]:
    illumina_dir = os.path.join(work_dir, "Illumina")
    return [
        File(os.path.join(illumina_dir, basename))
        for basename in os.listdir(illumina_dir)
    ]


@task()
def create_consolidated_tag_count(
    work_dir: str,
    enzyme: str,
    keyfile: File,
    job_context: JobContext,
    prefix: str = "",
) -> ConsolidatedTagCount:
    key_dir = os.path.join(work_dir, "key")
    os.makedirs(key_dir, exist_ok=True)
    key_path = os.path.join(key_dir, os.path.basename(keyfile.path))
    symlink_rel(keyfile.path, key_path, force=True)

    tagCounts_parts_dir = os.path.join(work_dir, "tagCounts_parts")
    tagCounts_dir = os.path.join(work_dir, "tagCounts")
    os.makedirs(tagCounts_parts_dir, exist_ok=True)

    part_dirs = ramify(keyfile=keyfile.path, output_folder=tagCounts_parts_dir)

    if len(part_dirs) > 1:
        stdout = {}
        tag_counts_list = []  # list of lists of tag count files

        for part_dir in part_dirs:
            fastq_to_tag_count = get_fastq_to_tag_count(
                work_dir=part_dir,
                enzyme=enzyme,
                keyfile=keyfile,
                fastq_files=illumina_fastq_files(part_dir),
                job_context=job_context,
            )
            stdout[prefixed(os.path.basename(part_dir), prefix=prefix)] = (
                fastq_to_tag_count.stdout
            )
            tag_counts_list.append(fastq_to_tag_count.tag_counts)

        return _merge_results_and_counts(
            work_dir=work_dir,
            parts_dir=tagCounts_parts_dir,
            part_dirs=part_dirs,
            merge_folder=tagCounts_dir,
            stdout=stdout,
            tag_counts_list=tag_counts_list,
            prefix=prefix,
        )

    else:
        fastq_to_tag_count = get_fastq_to_tag_count(
            work_dir=work_dir,
            enzyme=enzyme,
            keyfile=keyfile,
            fastq_files=illumina_fastq_files(work_dir),
            job_context=job_context,
        )

        tag_count = get_tag_count(fastq_to_tag_count.stdout, prefix=prefix)

        return ConsolidatedTagCount(
            tag_counts=fastq_to_tag_count.tag_counts,
            tag_count=tag_count,
            stdout={prefix: fastq_to_tag_count.stdout},
        )
