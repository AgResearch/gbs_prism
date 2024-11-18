import logging
import os.path
import time
from datetime import datetime, timedelta
from typing import Optional

from agr.gquery import GQuery, GQueryNotFoundException, Predicates
from agr.util import StdioRedirect

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
    def sample_sheet_path(self) -> str:
        return os.path.join(self._dir, "SampleSheet.csv")

    def await_complete(
        self,
        poll_interval: timedelta = timedelta(minutes=5),
        overall_timeout: Optional[timedelta] = None,
    ):
        self.validate()
        rta_complete_path = os.path.join(self._dir, "RTAComplete.txt")
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

    # TODO move this to a more appropriate class, perhaps
    def exists_in_database(self):
        """Use GQuery to determine whether the run exists in the database."""
        with open(os.devnull, "w") as devnull_f:
            with StdioRedirect(stdout=devnull_f, stderr=devnull_f):
                try:
                    GQuery(
                        task="lab_report",
                        predicates=Predicates(name="illumina_run_details"),
                        items=[self._run_name],
                    ).run()
                except GQueryNotFoundException:
                    return False
            return True
