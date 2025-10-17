import logging
from dataclasses import dataclass
from redun import task, File
from redun_psij import JobContext

from agr.redun.tasks.tag_count import (
    create_consolidated_tag_count,
)
from agr.redun.tasks.tassel3 import (
    merge_taxa_tag_count,
    tag_count_to_tag_pair,
    tag_pair_to_tbt,
    tbt_to_map_info,
    map_info_to_hap_map,
)

logger = logging.getLogger(__name__)


@dataclass
class DemultiplexOutput:
    tag_count: File
    fastq_to_tag_count_stdout: dict[str, File]
    hap_map_files: dict[str, File]

    @property
    def hap_map_file(self) -> File:
        return self.hap_map_files["HapMap.hmc.txt"]


@task()
def demultiplex(
    work_dir: str,
    enzyme: str,
    keyfile: File,
    job_context: JobContext,
    prefix: str = "",
    merge_taxa: bool = False,
) -> DemultiplexOutput:
    consolidated_tag_count = create_consolidated_tag_count(
        work_dir=work_dir,
        enzyme=enzyme,
        keyfile=keyfile,
        job_context=job_context,
        prefix=prefix,
    )
    merged_all_count = merge_taxa_tag_count(
        work_dir,
        consolidated_tag_count.tag_counts,
        merge=merge_taxa,
        job_context=job_context,
    )
    tag_pair = tag_count_to_tag_pair(
        work_dir, merged_all_count, job_context=job_context
    )
    tags_by_taxa = tag_pair_to_tbt(work_dir, tag_pair, job_context=job_context)
    map_info = tbt_to_map_info(work_dir, tags_by_taxa, job_context=job_context)
    hap_map_files = map_info_to_hap_map(work_dir, map_info, job_context=job_context)

    return DemultiplexOutput(
        tag_count=consolidated_tag_count.tag_count,
        fastq_to_tag_count_stdout=consolidated_tag_count.stdout,
        hap_map_files=hap_map_files,
    )
