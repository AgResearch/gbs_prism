import logging
import os.path
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SequencerRunError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self.msg = msg
        self.e = e


class SequencerRun(object):
    def __init__(self, seq_root: str, run: str):
        self.dir = os.path.join(seq_root, run)
        if not os.path.isdir(self.dir):
            raise SequencerRunError("no such directory %s" % self.dir)

    def ensure_dirs_exist(self):
        # validate it's a run directory
        run_info_path = os.path.join(self.dir, "RunInfo.xml")
        if not os.path.exists(run_info_path):
            raise SequencerRunError(
                "can't find %s, are you sure this is a run directory?" % run_info_path
            )

    @property
    def sample_sheet_path(self) -> str:
        return os.path.join(self.dir, "SampleSheet.csv")

    def await_complete(
        self,
        poll_interval: timedelta = timedelta(minutes=5),
        overall_timeout: Optional[timedelta] = None,
    ):
        self.ensure_dirs_exist()
        rta_complete_path = os.path.join(self.dir, "RTAComplete.txt")
        deadline = (
            datetime.now() + overall_timeout if overall_timeout is not None else None
        )
        while not os.path.exists(rta_complete_path) and (
            deadline is None or deadline < datetime.now()
        ):
            print(
                "%s does not exist, sleeping for %s"
                % (rta_complete_path, poll_interval)
            )
            logger.info(
                "%s does not exist, sleeping for %s"
                % (rta_complete_path, poll_interval)
            )
            time.sleep(poll_interval.total_seconds())
        if not os.path.exists(rta_complete_path):
            raise SequencerRunError("timeout waiting for %s" % rta_complete_path)
        logger.info("%s found, run is complete" % rta_complete_path)
