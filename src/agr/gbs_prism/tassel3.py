import logging
import os.path
import re
from typing import Any, Dict, List

import agr.util.cluster as cluster
from agr.util.path import remove_if_exists

from .enzyme_sub import enzyme_sub_for_uneak
from .types import Cohort

logger = logging.getLogger(__name__)


FASTQ_TO_TAG_COUNT_STDOUT = "stdout"
FASTQ_TO_TAG_COUNT_COUNTS = "counts"
HAP_MAP_FILES = "hap_map_files"


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
    def __init__(self, tool_context: Any):
        self._tool_context = tool_context

    def _jvm_args_for_plugin(self, plugin: str) -> List[str]:
        """Look up java_max_heap and java_initial_heap in tassel3 context for plugin, or fallback to default."""
        JAVA_MAX_HEAP = "java_max_heap"
        JAVA_INITIAL_HEAP = "java_initial_heap"
        max_heap = None
        initial_heap = None
        if isinstance(self._tool_context, dict):
            if isinstance(plugin_context := self._tool_context.get(plugin), dict):
                max_heap = plugin_context.get(JAVA_MAX_HEAP)
                initial_heap = plugin_context.get(JAVA_INITIAL_HEAP)
            if isinstance(default_context := self._tool_context.get("default"), dict):
                if max_heap is None:
                    max_heap = default_context.get(JAVA_MAX_HEAP)
                if initial_heap is None:
                    initial_heap = default_context.get(JAVA_INITIAL_HEAP)

        return ([f"-Xmx{max_heap}"] if max_heap is not None else []) + (
            [f"-Xms{initial_heap}"] if initial_heap is not None else []
        )

    def _tassel_plugin_job_1_spec(
        self,
        plugin: str,
        plugin_args: List[str],
        work_dir: str,
        result_path: str,
    ) -> cluster.Job1Spec:
        return cluster.Job1Spec(
            tool=f"tassel3_{plugin}",
            args=self._tassel_plugin_args(
                plugin,
                plugin_args,
                work_dir=work_dir,
            ),
            stdout_path=os.path.join(work_dir, "%s.stdout" % plugin),
            stderr_path=os.path.join(work_dir, "%s.stderr" % plugin),
            expected_path=result_path,
        )

    def _tassel_plugin_job_n_spec(
        self,
        plugin: str,
        plugin_args: List[str],
        work_dir: str,
        expected_paths: Dict[str, str],
        expected_globs: Dict[str, cluster.FilteredGlob],
    ) -> cluster.JobNSpec:
        return cluster.JobNSpec(
            tool=f"tassel3_{plugin}",
            args=self._tassel_plugin_args(
                plugin,
                plugin_args,
                work_dir=work_dir,
            ),
            stdout_path=os.path.join(work_dir, "%s.stdout" % plugin),
            stderr_path=os.path.join(work_dir, "%s.stderr" % plugin),
            expected_paths=expected_paths,
            expected_globs=expected_globs,
        )

    def _tassel_plugin_args(
        self, plugin: str, plugin_args: List[str], work_dir: str
    ) -> List[str]:
        return (
            [
                "run_pipeline.pl",
            ]
            + self._jvm_args_for_plugin(plugin)
            + [
                "-fork1",
                "-U%sPlugin" % plugin,
                "-w",
                work_dir,
            ]
            + plugin_args
            + [
                "-endPlugin",
                "-runfork1",
            ]
        )

    def _key_dir(self, work_dir: str) -> str:
        return os.path.join(work_dir, "key")

    #
    # tag_counts_part1_dir = os.path.join(cohort_blind_dir, "tagCounts_parts", "part1")
    # tag_counts_done = os.path.join(cohort_blind_dir, "tagCounts.done")

    def _tag_counts_dir(self, work_dir: str) -> str:
        return os.path.join(work_dir, "tagCounts")

    def _merged_tag_counts_dir(self, work_dir: str) -> str:
        return os.path.join(work_dir, "mergedTagCounts")

    def _tag_pair_dir(self, work_dir: str) -> str:
        return os.path.join(work_dir, "tagPair")

    def _tags_by_taxa_dir(self, work_dir: str) -> str:
        return os.path.join(work_dir, "tagsByTaxa")

    def _map_info_dir(self, work_dir: str) -> str:
        return os.path.join(work_dir, "mapInfo")

    def _hap_map_dir(self, work_dir: str) -> str:
        return os.path.join(work_dir, "hapMap")

    def create_directories(self, work_dir):
        # create all directories required by Tassel3, Illumina directory assumed to already exist
        os.makedirs(self._key_dir(work_dir), exist_ok=True)
        os.makedirs(self._merged_tag_counts_dir(work_dir), exist_ok=True)
        os.makedirs(self._tag_pair_dir(work_dir), exist_ok=True)
        os.makedirs(self._tags_by_taxa_dir(work_dir), exist_ok=True)
        os.makedirs(self._map_info_dir(work_dir), exist_ok=True)
        os.makedirs(self._hap_map_dir(work_dir), exist_ok=True)

    def symlink_key(self, in_path: str, work_dir: str):
        key_path = os.path.join(self._key_dir(work_dir), os.path.basename(in_path))
        remove_if_exists(key_path)
        logger.info("symlink %s %s" % (in_path, key_path))
        os.symlink(in_path, key_path)

    def fastq_to_tag_count_job_spec(
        self, cohort_str: str, work_dir: str
    ) -> cluster.JobNSpec:
        cohort = Cohort.parse(cohort_str)
        return self._tassel_plugin_job_n_spec(
            plugin="FastqToTagCount",
            plugin_args=[
                "-c",
                "1",
                "-e",
                enzyme_sub_for_uneak(cohort.enzyme),
                "-s",
                "900000000",
            ],
            work_dir=work_dir,
            expected_paths={
                FASTQ_TO_TAG_COUNT_STDOUT: os.path.join(
                    work_dir, "FastqToTagCount.stdout"
                ),
            },
            expected_globs={
                FASTQ_TO_TAG_COUNT_COUNTS: cluster.FilteredGlob(
                    "%s/*" % self._tag_counts_dir(work_dir)
                ),
            },
        )

    def merge_taxa_tag_count_job_spec(self, work_dir: str) -> cluster.Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin="MergeTaxaTagCount",
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
            work_dir=work_dir,
            result_path=os.path.join(
                self._merged_tag_counts_dir(work_dir), "mergedAll.cnt"
            ),
        )

    def tag_count_to_tag_pair_job_spec(self, work_dir: str) -> cluster.Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin="TagCountToTagPair",
            plugin_args=["-e", "0.03"],
            work_dir=work_dir,
            result_path=os.path.join(self._tag_pair_dir(work_dir), "tagPair.tps"),
        )

    def tag_pair_to_tbt_job_spec(self, work_dir: str) -> cluster.Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin="TagPairToTBT",
            plugin_args=[],
            work_dir=work_dir,
            result_path=os.path.join(self._tags_by_taxa_dir(work_dir), "tbt.bin"),
        )

    def tbt_to_map_info_job_spec(self, work_dir: str) -> cluster.Job1Spec:
        return self._tassel_plugin_job_1_spec(
            plugin="TBTToMapInfo",
            plugin_args=[],
            work_dir=work_dir,
            result_path=os.path.join(self._map_info_dir(work_dir), "mapInfo.bin"),
        )

    def map_info_to_hap_map_job_spec(self, work_dir: str) -> cluster.JobNSpec:
        return self._tassel_plugin_job_n_spec(
            plugin="MapInfoToHapMap",
            plugin_args=["-mnMAF", "0.03", "-mxMAF", "0.5", "-mnC", "0.1"],
            work_dir=work_dir,
            expected_paths={},
            expected_globs={
                HAP_MAP_FILES: cluster.FilteredGlob(
                    "%s/*" % self._hap_map_dir(work_dir)
                ),
            },
        )
