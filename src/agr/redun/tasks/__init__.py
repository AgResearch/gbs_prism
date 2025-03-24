# re-exports for agr.redun.tasks

from .bcl_convert import bcl_convert
from .bwa import bwa_aln_one, bwa_aln_all, bwa_samse_one, bwa_samse_all
from .cutadapt import cutadapt_one, cutadapt_all
from .dedupe import dedupe_one, dedupe_all
from .fake_bcl_convert import fake_bcl_convert, real_or_fake_bcl_convert
from .fastq_sample import fastq_sample_one, fastq_sample_all
from .fastqc import fastqc_one, fastqc_all
from .keyfiles import get_gbs_keyfiles, get_keyfile_for_tassel, get_keyfile_for_gbsx
from .kmer_analysis import kmer_analysis_one, kmer_analysis_all
from .multiqc import multiqc
from .sample_sheet import cook_sample_sheet
from .samtools import bam_stats_one, bam_stats_all
from .kgd import kgd
from .gusbase import gusbase
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
    "bam_stats_one",
    "bam_stats_all",
    "bcl_convert",
    "bwa_aln_one",
    "bwa_aln_all",
    "bwa_samse_one",
    "bwa_samse_all",
    "cook_sample_sheet",
    "cutadapt_one",
    "cutadapt_all",
    "dedupe_one",
    "dedupe_all",
    "fake_bcl_convert",
    "fastq_sample_one",
    "fastq_sample_all",
    "fastqc_one",
    "fastqc_all",
    "get_gbs_keyfiles",
    "get_keyfile_for_tassel",
    "get_keyfile_for_gbsx",
    "gusbase",
    "kgd",
    "kmer_analysis_one",
    "kmer_analysis_all",
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
