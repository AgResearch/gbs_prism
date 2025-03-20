# re-exports for agr.redun.tasks

from .bcl_convert import bcl_convert
from .fake_bcl_convert import fake_bcl_convert, real_or_fake_bcl_convert
from .fastq_sample import fastq_sample
from .fastqc import fastqc
from .multiqc import multiqc

__all__ = [
    "bcl_convert",
    "fake_bcl_convert",
    "fastq_sample",
    "fastqc",
    "multiqc",
    "real_or_fake_bcl_convert",
]
