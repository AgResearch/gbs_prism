import logging
import os.path
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class SequencerRunError(Exception):
    def __init__(self, msg: str, exc: Optional[Exception] = None):
        self.msg = msg
        self.exc = exc

class SequencerRun(object):
    def __init__(self, rootdir):
        if not os.path.exists(rootdir):
            raise SequencerRunError("no such directory %s" % rootdir)
        self.rootdir = rootdir
        
    def await_complete(self, poll_interval: timedelta = timedelta(minutes=5), overall_timeout: Optional[timedelta] = None):
        rta_complete_path = os.path.join(self.rootdir, "RTAComplete.txt")
        deadline = datetime.now() + overall_timeout if overall_timeout is not None else None
        while not os.path.exists(rta_complete_path) and (deadline is None or deadline < datetime.now()):
            print("%s does not exist, sleeping for %s" % (rta_complete_path, poll_interval))
            logger.info("%s does not exist, sleeping for %s" % (rta_complete_path, poll_interval))
            time.sleep(poll_interval.total_seconds())
        if not os.path.exists(rta_complete_path):
            raise SequencerRunError("timeout waiting for %s" % rta_complete_path)
        logger.info("%s found, run is complete" % rta_complete_path)
