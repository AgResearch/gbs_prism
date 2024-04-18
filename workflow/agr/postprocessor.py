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
        self.run_dir = os.path.join(postprocessing_root, run)
        if not os.path.isdir(postprocessing_root):
            raise PostProcessorError("no such directory %s" % postprocessing_root)

    @property
    def sample_sheet_path(self) -> str:
        return os.path.join(self.run_dir, "SampleSheet.csv")

    def ensure_run_dir_exists(self):
        try:
            os.makedirs(self.run_dir, exist_ok=True)
        except Exception as e:
            raise PostProcessorError("failed to create %s" % self.run_dir, e)
        logger.info("created %s directory" % self.run_dir)
