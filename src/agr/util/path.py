import errno
import os
from typing import Optional


def gunzipped(path: str) -> str:
    return path.removesuffix(".gz")


def gzipped(path: str) -> str:
    return "%s.gz" % path


def trimmed(fastq_filename: str) -> str:
    return "%s.trimmed.fastq" % fastq_filename.removesuffix(".gz").removesuffix(
        ".fastq"
    )


def prefixed(base: str, dir: Optional[str] = None, prefix: str = "") -> str:
    prefixed_base = f"{prefix}{"." if prefix else ""}{base}"
    return os.path.join(dir, prefixed_base) if dir is not None else prefixed_base


def baseroot(path: str) -> str:
    """
    Returns the root of the basename of the path, i.e. without any directories, and without anything
    after the first dot.
    """
    basename = os.path.basename(path)
    if (dot := basename.find(".")) != -1:
        return basename[:dot]
    else:
        return basename


def remove_if_exists(path: str):
    try:
        os.remove(path)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def symlink(
    src: str,
    dst: str,
    *,
    force=False,
    target_is_directory: bool = False,
    dir_fd: int | None = None,
):
    """Like os.symlink except supports a force argument, which Python should support natively, bah!."""
    if force:
        remove_if_exists(dst)
    os.symlink(src, dst, target_is_directory=target_is_directory, dir_fd=dir_fd)


def expand(path: str) -> str:
    """Expand both tildes and environment variables."""
    return os.path.expanduser(os.path.expandvars(path))
