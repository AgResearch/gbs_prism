import re
import subprocess
from typing import List


def capture_regex(
    args: List[str],
    capture: re.Pattern | str,
    from_stderr=False,
    default: str = "unknown",
) -> str:
    """
    Capture regex from stdout of process `args`, or from stderr if `from_stderr`
    """
    p = subprocess.run(args, text=True, capture_output=True)
    capture_re = re.compile(capture) if isinstance(capture, str) else capture
    if m := capture_re.match(p.stdout if not from_stderr else p.stderr):
        return m.group(1)
    else:
        return default
