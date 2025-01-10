import logging
import os.path
import pathlib
import re
import subprocess
from typing import Dict, List

from agr.util.path import remove_if_exists

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
    def __init__(
        self,
        initial_heap_size: str = "512M",
        max_heap_for_plugin: Dict[str, str] = {"FastqToTagCount": "5G"},
        default_max_heap: str = "20G",  # legacy used 500G
    ):
        self._initial_heap_size = initial_heap_size
        self._max_heap_for_plugin = max_heap_for_plugin
        self._default_max_heap = default_max_heap

    def _run_tassel_plugin(
        self, plugin: str, plugin_args: List[str], work_dir: str, done_file: str
    ):
        out_path = os.path.join(work_dir, "%s.stdout" % plugin)
        err_path = os.path.join(work_dir, "%s.stderr" % plugin)
        max_heap_size = self._max_heap_for_plugin.get(plugin, self._default_max_heap)
        with open(out_path, "w") as out_f:
            with open(err_path, "w") as err_f:
                tassel3_command = (
                    [
                        "run_pipeline.pl",
                        "-Xms%s" % self._initial_heap_size,
                        "-Xmx%s" % max_heap_size,
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
                _ = subprocess.run(
                    tassel3_command,
                    stdout=out_f,
                    stderr=err_f,
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
