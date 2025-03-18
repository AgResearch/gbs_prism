import logging
import os.path
import re
from typing import Any

import agr.util.cluster as cluster
from agr.util.path import symlink

from .enzyme_sub import enzyme_sub_for_uneak
from .types import Cohort

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
    cohort: Cohort, fcid: str, original_fastq_filename: str
) -> str:
    """Tassel3 is very fussy about what filenames it accepts for FASTQ files.

    This was cribbed from gquery/sequencing/illumina.py
    """
    lane_re = re.compile("_L00([0-9])_")
    if m := lane_re.search(original_fastq_filename):
        lane = m.group(1)
        return "%s_%s_s_%s_fastq.txt.gz" % (cohort.libname, fcid, lane)
    else:
        # return "%s_%s_s_X_fastq.txt.gz" % (cohort.libname, fcid)
        return original_fastq_filename


class Tassel3:
    def __init__(self, work_dir: str, tool_config: dict[str, Any]):
        self._work_dir = work_dir
        self._java_max_heap = tool_config.get("java_max_heap")
        self._java_initial_heap = tool_config.get("java_initial_heap")

    @property
    def _jvm_args(self) -> list[str]:
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
    ) -> cluster.Job1Spec:
        return cluster.Job1Spec(
            tool=tassel3_tool_name(plugin),
            args=self._tassel_plugin_args(
                plugin,
                plugin_args,
            ),
            stdout_path=os.path.join(self._work_dir, "%s.stdout" % plugin),
            stderr_path=os.path.join(self._work_dir, "%s.stderr" % plugin),
            expected_path=result_path,
        )

    def _tassel_plugin_job_n_spec(
        self,
        plugin: str,
        plugin_args: list[str],
        expected_paths: dict[str, str],
        expected_globs: dict[str, cluster.FilteredGlob],
    ) -> cluster.JobNSpec:
        return cluster.JobNSpec(
            tool=tassel3_tool_name(plugin),
            args=self._tassel_plugin_args(
                plugin,
                plugin_args,
            ),
            stdout_path=os.path.join(self._work_dir, "%s.stdout" % plugin),
            stderr_path=os.path.join(self._work_dir, "%s.stderr" % plugin),
            expected_paths=expected_paths,
            expected_globs=expected_globs,
        )

    def _tassel_plugin_args(self, plugin: str, plugin_args: list[str]) -> list[str]:
        return (
            [
                "run_pipeline.pl",
            ]
            + self._jvm_args
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
    def _key_dir(self) -> str:
        return os.path.join(self._work_dir, "key")

    #
    # tag_counts_part1_dir = os.path.join(cohort_blind_dir, "tagCounts_parts", "part1")
    # tag_counts_done = os.path.join(cohort_blind_dir, "tagCounts.done")

    @property
    def _tag_counts_dir(self) -> str:
        return os.path.join(self._work_dir, "tagCounts")

    @property
    def _merged_tag_counts_dir(self) -> str:
        return os.path.join(self._work_dir, "mergedTagCounts")

    @property
    def _tag_pair_dir(self) -> str:
        return os.path.join(self._work_dir, "tagPair")

    @property
    def _tags_by_taxa_dir(self) -> str:
        return os.path.join(self._work_dir, "tagsByTaxa")

    @property
    def _map_info_dir(self) -> str:
        return os.path.join(self._work_dir, "mapInfo")

    @property
    def _hap_map_dir(self) -> str:
        return os.path.join(self._work_dir, "hapMap")

    def create_directories(self):
        # create all directories required by Tassel3, Illumina directory assumed to already exist
        os.makedirs(self._key_dir, exist_ok=True)
        os.makedirs(self._tag_counts_dir, exist_ok=True)
        os.makedirs(self._merged_tag_counts_dir, exist_ok=True)
        os.makedirs(self._tag_pair_dir, exist_ok=True)
        os.makedirs(self._tags_by_taxa_dir, exist_ok=True)
        os.makedirs(self._map_info_dir, exist_ok=True)
        os.makedirs(self._hap_map_dir, exist_ok=True)

    def symlink_key(self, in_path: str):
        key_path = os.path.join(self._key_dir, os.path.basename(in_path))
        logger.info("symlink %s %s" % (in_path, key_path))
        symlink(in_path, key_path, force=True)

    def fastq_to_tag_count_job_spec(self, cohort_str: str) -> cluster.JobNSpec:
        cohort = Cohort.parse(cohort_str)
        return self._tassel_plugin_job_n_spec(
            plugin=FASTQ_TO_TAG_COUNT_PLUGIN,
            plugin_args=[
                "-c",
                "1",
                "-e",
                enzyme_sub_for_uneak(cohort.enzyme),
                "-s",
                "900000000",
            ],
            expected_paths={
                FASTQ_TO_TAG_COUNT_STDOUT: os.path.join(
                    self._work_dir, "%s.stdout" % FASTQ_TO_TAG_COUNT_PLUGIN
                ),
            },
            expected_globs={
                FASTQ_TO_TAG_COUNT_COUNTS: cluster.FilteredGlob(
                    "%s/*" % self._tag_counts_dir
                ),
            },
        )

    @property
    def merge_taxa_tag_count_job_spec(self) -> cluster.Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin=MERGE_TAXA_TAG_COUNT_PLUGIN,
            plugin_args=[
                "-t",
                "n",
                "-m",
                "600000000",
                "-x",
                "100000000",
                "-c",
                "5",
            ],
            result_path=os.path.join(self._merged_tag_counts_dir, "mergedAll.cnt"),
        )

    @property
    def tag_count_to_tag_pair_job_spec(self) -> cluster.Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin=TAG_COUNT_TO_TAG_PAIR_PLUGIN,
            plugin_args=["-e", "0.03"],
            result_path=os.path.join(self._tag_pair_dir, "tagPair.tps"),
        )

    @property
    def tag_pair_to_tbt_job_spec(self) -> cluster.Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin=TAG_PAIR_TO_TBT_PLUGIN,
            plugin_args=[],
            result_path=os.path.join(self._tags_by_taxa_dir, "tbt.bin"),
        )

    @property
    def tbt_to_map_info_job_spec(self) -> cluster.Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin=TBT_TO_MAP_INFO_PLUGIN,
            plugin_args=[],
            result_path=os.path.join(self._map_info_dir, "mapInfo.bin"),
        )

    @property
    def map_info_to_hap_map_job_spec(self) -> cluster.JobNSpec:
        return self._tassel_plugin_job_n_spec(
            plugin=MAP_INFO_TO_HAP_MAP_PLUGIN,
            plugin_args=["-mnMAF", "0.03", "-mxMAF", "0.5", "-mnC", "0.1"],
            expected_paths={},
            expected_globs={
                HAP_MAP_FILES: cluster.FilteredGlob("%s/*" % self._hap_map_dir),
            },
        )
