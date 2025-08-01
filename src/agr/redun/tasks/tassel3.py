import logging
import os
import re
import shutil
from dataclasses import dataclass
from redun import task, File
from typing import Any

from agr.util.path import symlink, prefixed
from agr.util.subprocess import run_catching_stderr
from agr.seq.enzyme_sub import enzyme_sub_for_uneak
from agr.redun.cluster_executor import (
    get_tool_config,
    run_job_1,
    run_job_n,
    Job1Spec,
    JobNSpec,
    ExpectedPaths,
    FilteredGlob,
)
from agr.redun import JobContext

logger = logging.getLogger(__name__)

FASTQ_TO_TAG_COUNT_PLUGIN = "FastqToTagCount"
MERGE_TAXA_TAG_COUNT_PLUGIN = "MergeTaxaTagCount"
TAG_COUNT_TO_TAG_PAIR_PLUGIN = "TagCountToTagPair"
TAG_PAIR_TO_TBT_PLUGIN = "TagPairToTBT"
MAP_INFO_TO_HAP_MAP_PLUGIN = "MapInfoToHapMap"
TBT_TO_MAP_INFO_PLUGIN = "TBTToMapInfo"

FASTQ_TO_TAG_COUNT_STDOUT = "stdout"
FASTQ_TO_TAG_COUNT_COUNTS = "counts"
HAP_MAP_FILES = "hap_map_files"


def tassel3_tool_name(plugin: str) -> str:
    return f"tassel3_{plugin}"


# TODO review this!!!
def fastq_name_for_tassel3(
    libname: str, fcid: str, original_fastq_filename: str
) -> str:
    """Tassel3 is very fussy about what filenames it accepts for FASTQ files.

    This was cribbed from gquery/sequencing/illumina.py
    """
    lane_re = re.compile("_L00([0-9])_")
    if m := lane_re.search(original_fastq_filename):
        lane = m.group(1)
        return "%s_%s_s_%s_fastq.txt.gz" % (libname, fcid, lane)
    else:
        # return "%s_%s_s_X_fastq.txt.gz" % (libname, fcid)
        return original_fastq_filename


class Tassel3:
    def __init__(
        self, work_dir: str, tool_config: dict[str, Any], job_context: JobContext
    ):
        self._work_dir = work_dir
        self._java_max_heap = tool_config.get("java_max_heap")
        self._java_initial_heap = tool_config.get("java_initial_heap")
        self._job_context = job_context

    @property
    def work_dir(self) -> str:
        return self._work_dir

    @property
    def jvm_args(self) -> list[str]:
        return (
            [f"-Xmx{self._java_max_heap}"] if self._java_max_heap is not None else []
        ) + (
            [f"-Xms{self._java_initial_heap}"]
            if self._java_initial_heap is not None
            else []
        )

    def _tassel_plugin_job_1_spec(
        self,
        plugin: str,
        plugin_args: list[str],
        result_path: str,
    ) -> Job1Spec:
        return Job1Spec(
            tool=tassel3_tool_name(plugin),
            args=self._tassel_plugin_args(
                plugin,
                plugin_args,
            ),
            stdout_path=os.path.join(self._work_dir, "%s.stdout" % plugin),
            stderr_path=os.path.join(self._work_dir, "%s.stderr" % plugin),
            custom_attributes=self._job_context.custom_attributes,
            expected_path=result_path,
        )

    def _tassel_plugin_job_n_spec(
        self,
        plugin: str,
        plugin_args: list[str],
        expected_paths: ExpectedPaths = ExpectedPaths(),
        expected_globs: dict[str, FilteredGlob] = {},
    ) -> JobNSpec:
        return JobNSpec(
            tool=tassel3_tool_name(plugin),
            args=self._tassel_plugin_args(
                plugin,
                plugin_args,
            ),
            stdout_path=os.path.join(self._work_dir, "%s.stdout" % plugin),
            stderr_path=os.path.join(self._work_dir, "%s.stderr" % plugin),
            custom_attributes=self._job_context.custom_attributes,
            expected_paths=expected_paths,
            expected_globs=expected_globs,
        )

    def _tassel_plugin_args(self, plugin: str, plugin_args: list[str]) -> list[str]:
        return (
            [
                "run_pipeline.pl",
            ]
            + self.jvm_args
            + [
                "-fork1",
                "-U%sPlugin" % plugin,
                "-w",
                self._work_dir,
            ]
            + plugin_args
            + [
                "-endPlugin",
                "-runfork1",
            ]
        )

    @property
    def key_dir(self) -> str:
        return os.path.join(self._work_dir, "key")

    @property
    def tag_counts_dir(self) -> str:
        return os.path.join(self._work_dir, "tagCounts")

    @property
    def merged_tag_counts_dir(self) -> str:
        return os.path.join(self._work_dir, "mergedTagCounts")

    @property
    def tag_pair_dir(self) -> str:
        return os.path.join(self._work_dir, "tagPair")

    @property
    def tags_by_taxa_dir(self) -> str:
        return os.path.join(self._work_dir, "tagsByTaxa")

    @property
    def map_info_dir(self) -> str:
        return os.path.join(self._work_dir, "mapInfo")

    @property
    def hap_map_dir(self) -> str:
        return hap_map_dir(self._work_dir)

    def symlink_key(self, in_path: str):
        os.makedirs(self.key_dir, exist_ok=True)
        key_path = os.path.join(self.key_dir, os.path.basename(in_path))
        logger.info("symlink %s %s" % (in_path, key_path))
        symlink(in_path, key_path, force=True)

    def fastq_to_tag_count_job_spec(self, enzyme: str) -> JobNSpec:
        return self._tassel_plugin_job_n_spec(
            plugin=FASTQ_TO_TAG_COUNT_PLUGIN,
            plugin_args=[
                "-e",
                enzyme_sub_for_uneak(enzyme),
                "-s",
                "900000000",
            ],
            expected_paths=ExpectedPaths(
                required={
                    FASTQ_TO_TAG_COUNT_STDOUT: os.path.join(
                        self._work_dir, "%s.stdout" % FASTQ_TO_TAG_COUNT_PLUGIN
                    ),
                }
            ),
            expected_globs={
                FASTQ_TO_TAG_COUNT_COUNTS: FilteredGlob("%s/*" % self.tag_counts_dir),
            },
        )

    def merge_taxa_tag_count_job_spec(self, merge: bool) -> Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin=MERGE_TAXA_TAG_COUNT_PLUGIN,
            plugin_args=[
                "-t",
                "y" if merge else "n",
            ],
            result_path=os.path.join(self.merged_tag_counts_dir, "mergedAll.cnt"),
        )

    @property
    def tag_count_to_tag_pair_job_spec(self) -> Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin=TAG_COUNT_TO_TAG_PAIR_PLUGIN,
            plugin_args=[],
            result_path=os.path.join(self.tag_pair_dir, "tagPair.tps"),
        )

    @property
    def tag_pair_to_tbt_job_spec(self) -> Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin=TAG_PAIR_TO_TBT_PLUGIN,
            plugin_args=[],
            result_path=os.path.join(self.tags_by_taxa_dir, "tbt.bin"),
        )

    @property
    def tbt_to_map_info_job_spec(self) -> Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin=TBT_TO_MAP_INFO_PLUGIN,
            plugin_args=[],
            result_path=os.path.join(self.map_info_dir, "mapInfo.bin"),
        )

    @property
    def map_info_to_hap_map_job_spec(self) -> JobNSpec:
        return self._tassel_plugin_job_n_spec(
            plugin=MAP_INFO_TO_HAP_MAP_PLUGIN,
            plugin_args=["-mnMAF", "0.03", "-mnC", "0.1"],
            expected_globs={
                HAP_MAP_FILES: FilteredGlob("%s/*" % self.hap_map_dir),
            },
        )


@dataclass
class FastqToTagCountOutput:
    stdout: File
    tag_counts: list[File]


@task()
def get_fastq_to_tag_count(
    work_dir: str, enzyme: str, keyfile: File, job_context: JobContext
) -> FastqToTagCountOutput:
    tassel3 = Tassel3(
        work_dir,
        get_tool_config(tassel3_tool_name(FASTQ_TO_TAG_COUNT_PLUGIN)),
        job_context=job_context,
    )
    # need to remove previous output in case we have a keyfile with different blindings,
    # to avoid overlaying new counts with old
    shutil.rmtree(tassel3.tag_counts_dir, ignore_errors=True)

    # and now ensure the output directory is present
    os.makedirs(tassel3.tag_counts_dir, exist_ok=True)

    tassel3.symlink_key(in_path=keyfile.path)
    result_files = run_job_n(tassel3.fastq_to_tag_count_job_spec(enzyme))

    return FastqToTagCountOutput(
        stdout=result_files.expected_files[FASTQ_TO_TAG_COUNT_STDOUT],
        tag_counts=result_files.globbed_files[FASTQ_TO_TAG_COUNT_COUNTS],
    )


def prefix_tag_count_path(out_dir: str, prefix: str = "") -> str:
    return prefixed("TagCount.csv", dir=out_dir, prefix=prefix)


@task()
def get_tag_count(fastqToTagCountStdout: File, prefix: str = "") -> File:
    out_path = prefix_tag_count_path(
        os.path.dirname(fastqToTagCountStdout.path), prefix=prefix
    )
    with open(fastqToTagCountStdout.path, "r") as in_f:
        with open(out_path, "w") as out_f:
            _ = run_catching_stderr(
                ["get_reads_tags_per_sample"], stdin=in_f, stdout=out_f, check=True
            )
    return File(out_path)


@task()
def merge_taxa_tag_count(
    work_dir: str, tag_counts: list[File], merge: bool, job_context: JobContext
) -> File:
    _ = tag_counts  # depending on existence rather than value
    tassel3 = Tassel3(
        work_dir,
        get_tool_config(tassel3_tool_name(MERGE_TAXA_TAG_COUNT_PLUGIN)),
        job_context=job_context,
    )
    os.makedirs(tassel3.merged_tag_counts_dir, exist_ok=True)

    return run_job_1(
        tassel3.merge_taxa_tag_count_job_spec(merge),
    )


@task()
def tag_count_to_tag_pair(
    work_dir: str, merged_all_count: File, job_context: JobContext
) -> File:
    _ = merged_all_count  # depending on existence rather than value
    tassel3 = Tassel3(
        work_dir,
        get_tool_config(tassel3_tool_name(TAG_COUNT_TO_TAG_PAIR_PLUGIN)),
        job_context=job_context,
    )
    os.makedirs(tassel3.tag_pair_dir, exist_ok=True)

    return run_job_1(
        tassel3.tag_count_to_tag_pair_job_spec,
    )


@task()
def tag_pair_to_tbt(work_dir: str, tag_pair: File, job_context: JobContext) -> File:
    _ = tag_pair  # depending on existence rather than value
    tassel3 = Tassel3(
        work_dir,
        get_tool_config(tassel3_tool_name(TAG_PAIR_TO_TBT_PLUGIN)),
        job_context=job_context,
    )
    os.makedirs(tassel3.tags_by_taxa_dir, exist_ok=True)

    return run_job_1(
        tassel3.tag_pair_to_tbt_job_spec,
    )


@task()
def tbt_to_map_info(work_dir: str, tags_by_taxa: File, job_context: JobContext) -> File:
    _ = tags_by_taxa  # depending on existence rather than value
    tassel3 = Tassel3(
        work_dir,
        get_tool_config(tassel3_tool_name(TBT_TO_MAP_INFO_PLUGIN)),
        job_context=job_context,
    )
    os.makedirs(tassel3.map_info_dir, exist_ok=True)

    return run_job_1(
        tassel3.tbt_to_map_info_job_spec,
    )


@task()
def map_info_to_hap_map(
    work_dir: str, map_info: File, job_context: JobContext
) -> list[File]:
    _ = map_info  # depending on existence rather than value
    tassel3 = Tassel3(
        work_dir,
        get_tool_config(tassel3_tool_name(MAP_INFO_TO_HAP_MAP_PLUGIN)),
        job_context=job_context,
    )
    os.makedirs(tassel3.hap_map_dir, exist_ok=True)

    result_files = run_job_n(
        tassel3.map_info_to_hap_map_job_spec,
    )
    return result_files.globbed_files[HAP_MAP_FILES]


def hap_map_dir(work_dir: str) -> str:
    return os.path.join(work_dir, "hapMap")
