import re
from typing import List

from agr.util.subprocess import capture_regex


def write_version(
    process_name: str,
    program_name: str,
    program_version_command: List[str],
    program_version_capture_regex: re.Pattern | str,
    from_stderr=False,
    default: str = "unknown",
    versions_yaml_path: str = "versions.yml",
):
    version = capture_regex(
        program_version_command,
        program_version_capture_regex,
        from_stderr=from_stderr,
        default=default,
    )
    with open(versions_yaml_path, "w") as versions_f:
        _ = versions_f.write("%s:\n  %s: %s\n" % (process_name, program_name, version))
