import logging
import os.path
import re

LEGACY_MOUNTPOINT_RE = re.compile(r"/bifo/([^/]+)/([^/]+)(.*)$")

logger = logging.getLogger(__name__)


def sanitised_realpath(path: str) -> str:
    realpath = os.path.realpath(path)
    # don't let the actual mountpoints leak, since these are not supported on eRI
    if m := LEGACY_MOUNTPOINT_RE.match(realpath):
        sanitised_realpath = "/dataset/%s/%s%s" % (m.group(2), m.group(1), m.group(3))
        logger.debug(
            'sanitised_realpath("%s") = "%s", not "%s"'
            % (path, sanitised_realpath, realpath)
        )
        return sanitised_realpath
    else:
        return realpath
