from dataclasses import dataclass
from typing import Optional


@dataclass(kw_only=True)
class CommonJobSpec:
    """The spec in common for any job to run on the compute cluster."""

    tool: str
    args: list[str]
    stdout_path: str
    stderr_path: str
    cwd: Optional[str] = None


@dataclass(kw_only=True)
class Job1Spec(CommonJobSpec):
    """For jobs which produce a single file whose path is known in advance."""

    expected_path: str


@dataclass
class FilteredGlob:
    """A file glob optionally without any paths matched by `reject_re`."""

    glob: str
    reject_re: Optional[str] = None


@dataclass(kw_only=True)
class JobNSpec(CommonJobSpec):
    """
    For jobs which produce multiple files with paths matching the glob, exluding any matched by the regex.

    As many conbinations of globs and paths may be expected, in a dict whose keys are arbitrary strings.
    Result files will be returned in a dict with the same keys.
    """

    # each value is either a result path or a filtered glob
    expected_paths: dict[str, str]
    expected_globs: dict[str, FilteredGlob]
