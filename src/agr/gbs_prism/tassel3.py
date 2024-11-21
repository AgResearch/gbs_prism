import logging
import os.path
import subprocess

from agr.util.path import remove_if_exists

from .enzyme_sub import enzyme_sub_for_uneak
from .types import Cohort

logger = logging.getLogger(__name__)


class Tassel3:
    def __init__(self, initial_heap_size: str = "512M", max_heap_size: str = "5G"):
        self._initial_heap_size = initial_heap_size
        self._max_heap_size = max_heap_size

    @property
    def moniker(self) -> str:
        return "B%d" % self._max_heap_size

    def fastq_to_tag_count(self, in_path: str, cohort_str: str, out_dir: str):
        cohort = Cohort.parse(cohort_str)

        # TODO create key directory as required by Tassel3, Illumina dir assumed to already exist
        key_dir = os.path.join(out_dir, "key")
        key_path = os.path.join(key_dir, os.path.basename(in_path))
        os.makedirs(key_dir, exist_ok=True)
        remove_if_exists(key_path)
        logger.info("symlink %s %s" % (in_path, key_path))
        os.symlink(in_path, key_path)

        tag_counts_dir = os.path.join(out_dir, "tagCounts")
        os.makedirs(tag_counts_dir, exist_ok=True)

        out_path = os.path.join(out_dir, "FastqToTagCount.stdout")
        err_path = os.path.join(out_dir, "FastqToTagCount.stderr")
        with open(out_path, "w") as out_f:
            with open(err_path, "w") as err_f:
                tassel3_command = [
                    "run_pipeline.pl",
                    "-Xms%s" % self._initial_heap_size,
                    "-Xmx%s" % self._max_heap_size,
                    "-fork1",
                    "-UFastqToTagCountPlugin",
                    "-w",
                    out_dir,
                    "-c",
                    "1",
                    "-e",
                    enzyme_sub_for_uneak(cohort.enzyme),
                    "-s",
                    "900000000",
                    "-endPlugin",
                    "-runfork1",
                ]
                logger.info(" ".join(tassel3_command))
                _ = subprocess.run(
                    tassel3_command,
                    stdout=out_f,
                    stderr=err_f,
                    check=True,
                )
