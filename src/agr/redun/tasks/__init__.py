# re-exports for agr.redun.tasks

from .bcl_convert import bcl_convert
from .dedupe import dedupe
from .fake_bcl_convert import fake_bcl_convert, real_or_fake_bcl_convert
from .fastq_sample import fastq_sample
from .fastqc import fastqc
from .kmer_analysis import kmer_analysis
from .multiqc import multiqc
from .sample_sheet import cook_sample_sheet

__all__ = [
    "bcl_convert",
    "cook_sample_sheet",
    "dedupe",
    "fake_bcl_convert",
    "fastq_sample",
    "fastqc",
    "kmer_analysis",
    "multiqc",
    "real_or_fake_bcl_convert",
]
