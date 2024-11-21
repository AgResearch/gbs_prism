import errno
import os


def gunzipped(path: str) -> str:
    return path.removesuffix(".gz")


def gzipped(path: str) -> str:
    return "%s.gz" % path


def trimmed(fastq_filename: str) -> str:
    return "%s.trimmed.fastq" % fastq_filename.removesuffix(".gz").removesuffix(
        ".fastq"
    )


def remove_if_exists(path: str):
    try:
        os.remove(path)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
