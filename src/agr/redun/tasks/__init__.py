# re-exports for agr.redun.tasks

from .bcl_convert import bcl_convert
from .fake_bcl_convert import fake_bcl_convert, real_or_fake_bcl_convert
from .fastqc import fastqc

__all__ = [
    "bcl_convert",
    "fake_bcl_convert",
    "fastqc",
    "real_or_fake_bcl_convert",
]
