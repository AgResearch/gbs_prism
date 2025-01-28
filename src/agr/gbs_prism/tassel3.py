import logging
import os.path
import pathlib
import re
from typing import Any, List

from agr.util.path import remove_if_exists
from agr.util.subprocess import run_catching_stderr

from .enzyme_sub import enzyme_sub_for_uneak
from .types import Cohort

logger = logging.getLogger(__name__)


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
    def __init__(self, tassel3_context: Any):
        self._context = tassel3_context

    def _jvm_args_for_plugin(self, plugin: str) -> List[str]:
        """Look up java_max_heap and java_initial_heap in tassel3 context for plugin, or fallback to default."""
        JAVA_MAX_HEAP = "java_max_heap"
        JAVA_INITIAL_HEAP = "java_initial_heap"
        max_heap = None
        initial_heap = None
        if isinstance(self._context, dict):
            if isinstance(plugin_context := self._context.get(plugin), dict):
                max_heap = plugin_context.get(JAVA_MAX_HEAP)
                initial_heap = plugin_context.get(JAVA_INITIAL_HEAP)
            if isinstance(default_context := self._context.get("default"), dict):
                if max_heap is None:
                    max_heap = default_context.get(JAVA_MAX_HEAP)
                if initial_heap is None:
                    initial_heap = default_context.get(JAVA_INITIAL_HEAP)

        return ([f"-Xmx{max_heap}"] if max_heap is not None else []) + (
            [f"-Xms{initial_heap}"] if initial_heap is not None else []
        )

    def _run_tassel_plugin(
        self, plugin: str, plugin_args: List[str], work_dir: str, done_file: str
    ):
        out_path = os.path.join(work_dir, "%s.stdout" % plugin)
        with open(out_path, "w") as out_f:
            tassel3_command = (
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
            logger.info(" ".join(tassel3_command))
            _ = run_catching_stderr(
                tassel3_command,
                stdout=out_f,
                check=True,
            )
        pathlib.Path(os.path.join(work_dir, done_file)).touch()

    def fastq_to_tag_count(self, in_path: str, cohort_str: str, work_dir: str):
        cohort = Cohort.parse(cohort_str)

        # TODO create key directory as required by Tassel3, Illumina dir assumed to already exist
        key_dir = os.path.join(work_dir, "key")
        key_path = os.path.join(key_dir, os.path.basename(in_path))
        os.makedirs(key_dir, exist_ok=True)
        remove_if_exists(key_path)
        logger.info("symlink %s %s" % (in_path, key_path))
        os.symlink(in_path, key_path)

        tag_counts_dir = os.path.join(work_dir, "tagCounts")
        os.makedirs(tag_counts_dir, exist_ok=True)

        self._run_tassel_plugin(
            "FastqToTagCount",
            [
                "-c",
                "1",
                "-e",
                enzyme_sub_for_uneak(cohort.enzyme),
                "-s",
                "900000000",
            ],
            work_dir=work_dir,
            done_file="tagCounts.done",
        )

    def merge_taxa_tag_count(self, work_dir: str):
        merged_tag_counts_dir = os.path.join(work_dir, "mergedTagCounts")
        os.makedirs(merged_tag_counts_dir, exist_ok=True)

        self._run_tassel_plugin(
            "MergeTaxaTagCount",
            [
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
            done_file="mergedTagCounts.done",
        )

    def tag_count_to_tag_pair(self, work_dir: str):
        tag_pair_dir = os.path.join(work_dir, "tagPair")
        os.makedirs(tag_pair_dir, exist_ok=True)

        self._run_tassel_plugin(
            "TagCountToTagPair",
            ["-e", "0.03"],
            work_dir=work_dir,
            done_file="tagPair.done",
        )

    def tag_pair_to_tbt(self, work_dir: str):
        tags_by_taxa_dir = os.path.join(work_dir, "tagsByTaxa")
        os.makedirs(tags_by_taxa_dir, exist_ok=True)

        self._run_tassel_plugin(
            "TagPairToTBT",
            [],
            work_dir=work_dir,
            done_file="tagsByTaxa.done",
        )

    def tbt_to_map_info(self, work_dir: str):
        map_info_dir = os.path.join(work_dir, "mapInfo")
        os.makedirs(map_info_dir, exist_ok=True)

        self._run_tassel_plugin(
            "TBTToMapInfo",
            [],
            work_dir=work_dir,
            done_file="mapInfo.done",
        )

    def map_info_to_hap_map(self, work_dir: str):
        hap_map_dir = os.path.join(work_dir, "hapMap")
        os.makedirs(hap_map_dir, exist_ok=True)

        self._run_tassel_plugin(
            "MapInfoToHapMap",
            ["-mnMAF", "0.03", "-mxMAF", "0.5", "-mnC", "0.1"],
            work_dir=work_dir,
            done_file="hapMap.done",
        )
