from dataclasses import dataclass
from typing import List, Optional


@dataclass(kw_only=True)
class CommonJobSpec:
    """The spec in common for any job to run on the compute cluster."""

    tool: str
    args: List[str]
    stdout_path: str
    stderr_path: str
    cwd: Optional[str] = None
    comment: Optional[str] = None


@dataclass(kw_only=True)
class Job1Spec(CommonJobSpec):
    """For jobs which produce a single file whose path is known in advance."""

    result_path: str


@dataclass(kw_only=True)
class JobNSpec(CommonJobSpec):
    """For jobs which produce multiple files with paths matching the glob, exluding any matched by the regex."""

    result_glob: str
    result_reject_re: Optional[str] = None
