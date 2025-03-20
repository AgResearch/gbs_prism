# re-exports for agr.redun.tasks

from .bcl_convert import bcl_convert
from .bwa import bwa_aln, bwa_samse
from .cutadapt import cutadapt
from .dedupe import dedupe
from .fake_bcl_convert import fake_bcl_convert, real_or_fake_bcl_convert
from .fastq_sample import fastq_sample
from .fastqc import fastqc
from .keyfiles import get_gbs_keyfiles, get_keyfile_for_tassel, get_keyfile_for_gbsx
from .kmer_analysis import kmer_analysis
from .multiqc import multiqc
from .sample_sheet import cook_sample_sheet
from .samtools import bam_stats
from .kgd import kgd
from .tassel3 import (
    get_fastq_to_tag_count,
    get_tag_count,
    get_tags_reads_summary,
    get_tags_reads_cv,
    merge_taxa_tag_count,
    tag_count_to_tag_pair,
    tag_pair_to_tbt,
    tbt_to_map_info,
    map_info_to_hap_map,
)

__all__ = [
    "bam_stats",
    "bcl_convert",
    "bwa_aln",
    "bwa_samse",
    "cook_sample_sheet",
    "cutadapt",
    "dedupe",
    "fake_bcl_convert",
    "fastq_sample",
    "fastqc",
    "get_gbs_keyfiles",
    "get_keyfile_for_tassel",
    "get_keyfile_for_gbsx",
    "kgd",
    "kmer_analysis",
    "multiqc",
    "real_or_fake_bcl_convert",
    # Tassel:
    "get_fastq_to_tag_count",
    "get_tag_count",
    "get_tags_reads_summary",
    "get_tags_reads_cv",
    "merge_taxa_tag_count",
    "tag_count_to_tag_pair",
    "tag_pair_to_tbt",
    "tbt_to_map_info",
    "map_info_to_hap_map",
]
