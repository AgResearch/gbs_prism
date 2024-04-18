import logging
import os.path
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class PostProcessorError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self.msg = msg
        self.e = e

    def __str__(self) -> str:
        return "%s: %s" % (self.msg, str(self.e))

class PostProcessor(object):
    def __init__(self, postprocessing_root: str, run: str):
        self.dir = os.path.join(postprocessing_root, run)
        if not os.path.isdir(postprocessing_root):
            raise PostProcessorError("no such directory %s" % postprocessing_root)

    @property
    def sample_sheet_path(self) -> str:
        return os.path.join(self.dir, "SampleSheet.csv")

    @property
    def sample_sheet_dir(self) -> str:
        return os.path.join(self.dir, "SampleSheet")

    @property
    def bclconvert_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "bclconvert")

    @property
    def top_unknown_path(self) -> str:
        return os.path.join(self.bclconvert_dir, "Reports", "Top_Unknown_Barcodes.csv")

    @property
    def fastq_complete_path(self) -> str:
        return os.path.join(self.bclconvert_dir, "Logs", "FastqComplete.txt")

    def ensure_dirs_exist(self):
        try:
            os.makedirs(self.sample_sheet_dir, exist_ok=True)
        except Exception as e:
            raise PostProcessorError("failed to create %s" % self.sample_sheet_dir, e)
        logger.info("created %s directory" % self.sample_sheet_dir)
