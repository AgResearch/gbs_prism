import logging
import os
import os.path
import time
from datetime import datetime, timedelta
from typing import Optional

from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


class SequencerRunError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e


class SequencerRun:
    def __init__(self, seq_root: str, run_name: str):
        self._seq_root = seq_root
        self._run_name = run_name
        self._dir = os.path.join(seq_root, run_name)
        if not os.path.isdir(self._dir):
            raise SequencerRunError("no such directory %s" % self._dir)

    def validate(self):
        # validate it's a run directory
        run_info_path = os.path.join(self._dir, "RunInfo.xml")
        if not os.path.exists(run_info_path):
            raise SequencerRunError(
                "can't find %s, are you sure this is a run directory?" % run_info_path
            )

    @property
    def seq_root(self) -> str:
        return self._seq_root

    @property
    def dir(self) -> str:
        return self._dir

    @property
    def name(self) -> str:
        return self._run_name

    @property
    def sample_sheet_path(self) -> str:
        return os.path.join(self._dir, "SampleSheet.csv")

    def await_complete(
        self,
        poll_interval: timedelta = timedelta(minutes=5),
        overall_timeout: Optional[timedelta] = None,
    ):
        self.validate()
        copy_complete_path = os.path.join(self._dir, "CopyComplete.txt")
        deadline = (
            datetime.now() + overall_timeout if overall_timeout is not None else None
        )
        while not os.path.exists(copy_complete_path) and (
            deadline is None or deadline < datetime.now()
        ):
            print(
                "%s does not exist, sleeping for %s"
                % (copy_complete_path, poll_interval)
            )
            logger.info(
                "%s does not exist, sleeping for %s"
                % (copy_complete_path, poll_interval)
            )
            time.sleep(poll_interval.total_seconds())
        if not os.path.exists(copy_complete_path):
            raise SequencerRunError("timeout waiting for %s" % copy_complete_path)
        logger.info("%s found, run is complete" % copy_complete_path)

    # TODO move this to a more appropriate class, perhaps
    def exists_in_database(self):
        """Use GQuery to determine whether the run exists in the database."""
        # TODO: there ought to be a nicer way to do this than failure code from gquery subprocess
        with open("/dev/null", "wb") as devnull_f:
            gquery = run_catching_stderr(
                [
                    "gquery",
                    "-t",
                    "lab_report",
                    "-p",
                    "name=illumina_run_details",
                    self._run_name,
                ],
                stdout=devnull_f,
                stderr=devnull_f,
            )
            return gquery.returncode == 0
