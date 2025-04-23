import os.path
from dataclasses import dataclass
from agr.redun.tasks.gupdate import import_gbs_kgd_stats
from redun import task, File
from typing import Optional

redun_namespace = "agr.gbs_prism"

from agr.util.legacy import sanitised_realpath
from agr.util.path import symlink
from agr.redun import concat, lazy_map

from agr.gbs_prism.paths import GbsPaths
from agr.gbs_prism.gbs_target_spec import CohortTargetSpec, GbsTargetSpec
from agr.seq.types import flowcell_id, Cohort
from agr.redun.tasks import (
    bam_stats_all,
    bwa_aln_all,
    bwa_samse_all,
    collate_tags_reads,
    collate_tags_reads_kgdstats,
    cutadapt_all,
    fastq_sample_all,
    get_keyfile_for_tassel,
    get_keyfile_for_gbsx,
    gusbase,
    kgd,
    import_gbs_read_tag_counts,
    create_cohort_gbs_kgd_stats_import,
    # Tassel:
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
from agr.redun.tasks.bwa import Bwa
from agr.redun.tasks.fastq_sample import FastqSampleSpec
from agr.redun.tasks.tassel3 import fastq_name_for_tassel3, hap_map_dir
from agr.redun.tasks.kgd import KgdOutput, kgd_dir
from agr.redun.tasks.unblind import (
    get_unblind_script,
    unblind_one,
    unblind_all,
    unblind_each,
)


@dataclass
class CohortSpec:
    run: str
    cohort: Cohort
    target: CohortTargetSpec
    paths: GbsPaths
    bwa_sample: FastqSampleSpec
    bwa: Bwa


@task
def create_cohort_fastq_links(spec: CohortSpec) -> tuple[list[File], list[File]]:
    """Link the fastq files for a single cohort separately.

    So that subsequent dependencies can be properly captured in wildcarded paths.
    """
    cohort_links = []
    cohort_munged_links = []
    for fastq_basename, fastq_link in spec.target.fastq_links.items():
        # create the same links in both blind and unblind directories
        for blind in [False, True]:
            link_dir = spec.paths.fastq_link_dir(str(spec.cohort.name), blind=blind)
            os.makedirs(link_dir, exist_ok=True)
            link = os.path.join(
                link_dir,
                (
                    # the blind directory is solely for Tassel3 which ironically can't see .fastq.gz files
                    fastq_basename
                    if not blind
                    else fastq_name_for_tassel3(
                        spec.cohort, flowcell_id(spec.run), fastq_basename
                    )
                ),
            )
            symlink(sanitised_realpath(fastq_link), link, force=True)
            if blind:
                cohort_munged_links.append(File(link))
            else:
                cohort_links.append(File(link))
    return (cohort_links, cohort_munged_links)


@task()
def bwa_all_reference_genomes(fastq_files: list[File], spec: CohortSpec) -> list[File]:
    """bwa_aln and bwa_samse for each file for each of the reference genomes."""
    out_dir = spec.paths.bwa_mapping_dir(spec.cohort.name)
    os.makedirs(out_dir, exist_ok=True)
    out_paths = []
    for ref_name, ref_path in spec.target.alignment_references.items():
        alns = bwa_aln_all(
            fastq_files,
            ref_name=ref_name,
            ref_path=ref_path,
            bwa=spec.bwa,
            out_dir=out_dir,
        )
        bam_files = bwa_samse_all(
            alns,
            ref_path=ref_path,
        )
        out_paths = concat(out_paths, bam_files)
    return out_paths


@dataclass
class CohortOutput:
    # TODO remove the ones we don't need
    fastq_links: list[File]
    munged_fastq_links_for_tassel: list[File]
    bwa_sampled: list[File]
    trimmed: list[File]
    bam_files: list[File]
    bam_stats_files: list[File]
    keyfile_for_tassel: File
    keyfile_for_gbsx: File
    tag_count: File
    collated_tag_count: File
    imported_gbs_read_tag_counts_marker: File
    tags_reads_summary: File
    tags_reads_cv: File
    merged_all_count: File
    tag_pair: File
    tags_by_taxa: File
    map_info: File
    hap_map_files: list[File]
    kgd_output: KgdOutput
    gbs_kgd_stats_import: Optional[File]
    collated_kgd_stats: Optional[File]
    gusbase_comet: Optional[File]
    tag_count_unblind: File
    hap_map_files_unblind: list[File]
    kgd_data_files_unblind: dict[str, File]


def cohort_gbs_kgd_stats_import(cohort_output: CohortOutput) -> Optional[File]:
    return cohort_output.gbs_kgd_stats_import


@task()
def run_cohort(spec: CohortSpec) -> CohortOutput:
    """Run the entire pipeline for a single cohort."""

    fastq_links, munged_fastq_links_for_tassel = create_cohort_fastq_links(spec)

    bwa_sampled = fastq_sample_all(
        fastq_links,
        spec=spec.bwa_sample,
        out_dir=spec.paths.bwa_mapping_dir(spec.cohort.name),
    )

    trimmed = cutadapt_all(
        bwa_sampled, out_dir=spec.paths.bwa_mapping_dir(spec.cohort.name)
    )

    bam_files = bwa_all_reference_genomes(trimmed, spec)
    bam_stats_files = bam_stats_all(bam_files)

    keyfile_for_tassel = get_keyfile_for_tassel(
        spec.paths.run_root, spec.run, spec.cohort
    )
    keyfile_for_gbsx = get_keyfile_for_gbsx(spec.paths.run_root, spec.run, spec.cohort)

    cohort_blind_dir = spec.paths.cohort_blind_dir(spec.cohort.name)
    unblind_script = get_unblind_script(
        spec.paths.cohort_blind_dir(spec.cohort.name),
        flowcell_id(spec.run),
        spec.cohort.enzyme,
        spec.cohort.gbs_cohort,
        spec.cohort.libname,
    )

    fastq_to_tag_count = get_fastq_to_tag_count(
        cohort_blind_dir, spec.cohort, keyfile_for_tassel
    )

    tag_count = get_tag_count(fastq_to_tag_count.stdout)
    collated_tag_count = collate_tags_reads(
        run=spec.run,
        cohort=spec.cohort.name,
        tag_counts=tag_count,
        out_path=os.path.join(
            spec.paths.cohort_blind_dir(spec.cohort.name), "CollatedTagCount.tsv"
        ),
    )
    imported_gbs_read_tag_counts_marker = import_gbs_read_tag_counts(
        run=spec.run, collated_tag_count=collated_tag_count
    )

    tags_reads_summary = get_tags_reads_summary(
        spec.paths.cohort_dir(spec.cohort.name), tag_count
    )
    tags_reads_cv = get_tags_reads_cv(tags_reads_summary)

    merged_all_count = merge_taxa_tag_count(
        cohort_blind_dir, fastq_to_tag_count.tag_counts
    )
    tag_pair = tag_count_to_tag_pair(cohort_blind_dir, merged_all_count)
    tags_by_taxa = tag_pair_to_tbt(cohort_blind_dir, tag_pair)
    map_info = tbt_to_map_info(cohort_blind_dir, tags_by_taxa)
    hap_map_files = map_info_to_hap_map(cohort_blind_dir, map_info)

    tag_count_unblind = unblind_one(
        tag_count, unblind_script, spec.paths.cohort_dir(spec.cohort.name)
    )
    hap_map_files_unblind = unblind_all(
        hap_map_files,
        unblind_script,
        hap_map_dir(spec.paths.cohort_dir(spec.cohort.name)),
    )

    kgd_output = kgd(cohort_blind_dir, spec.target.genotyping_method, hap_map_files)

    collated_kgd_stats = collate_tags_reads_kgdstats(
        run=spec.run,
        cohort=spec.cohort.name,
        tag_counts=tag_count,
        kgd_stats=kgd_output.sample_stats_csv,
        out_path=os.path.join(
            spec.paths.cohort_blind_dir(spec.cohort.name),
            "TagCountsAndSampleStats.csv",
        ),
    )

    gbs_kgd_stats_import = create_cohort_gbs_kgd_stats_import(
        run=spec.run,
        cohort_name=spec.cohort.name,
        kgd_stats_csv=kgd_output.sample_stats_csv,
    )

    gusbase_comet = gusbase(kgd_output.gusbase_rdata)

    kgd_data_files_unblind = unblind_each(
        kgd_output.data_files,
        unblind_script,
        kgd_dir(spec.paths.cohort_dir(spec.cohort.name)),
    )

    output = CohortOutput(
        fastq_links=fastq_links,
        munged_fastq_links_for_tassel=munged_fastq_links_for_tassel,
        bwa_sampled=bwa_sampled,
        trimmed=trimmed,
        bam_files=bam_files,
        bam_stats_files=bam_stats_files,
        keyfile_for_tassel=keyfile_for_tassel,
        keyfile_for_gbsx=keyfile_for_gbsx,
        tag_count=tag_count,
        collated_tag_count=collated_tag_count,
        imported_gbs_read_tag_counts_marker=imported_gbs_read_tag_counts_marker,
        tags_reads_summary=tags_reads_summary,
        tags_reads_cv=tags_reads_cv,
        merged_all_count=merged_all_count,
        tag_pair=tag_pair,
        tags_by_taxa=tags_by_taxa,
        map_info=map_info,
        hap_map_files=hap_map_files,
        kgd_output=kgd_output,
        gbs_kgd_stats_import=gbs_kgd_stats_import,
        collated_kgd_stats=collated_kgd_stats,
        gusbase_comet=gusbase_comet,
        tag_count_unblind=tag_count_unblind,
        hap_map_files_unblind=hap_map_files_unblind,
        kgd_data_files_unblind=kgd_data_files_unblind,
    )
    return output


@dataclass
class Stage2Output:
    cohorts: dict[str, CohortOutput]
    imported_gbs_kgd_stats: File


@task()
def run_stage2(run: str, spec: GbsTargetSpec, gbs_paths: GbsPaths) -> Stage2Output:
    cohort_outputs = {}

    bwa_sample = FastqSampleSpec(
        rate=0.00005,
        minimum_sample_size=150000,
    )

    bwa = Bwa(barcode_len=10)

    for name, target in spec.cohorts.items():
        cohort = Cohort.parse(name)
        target = CohortSpec(
            run=run,
            cohort=cohort,
            target=target,
            paths=gbs_paths,
            bwa_sample=bwa_sample,
            bwa=bwa,
        )

        cohort_outputs[name] = run_cohort(target)

    imported_gbs_kgd_stats = import_gbs_kgd_stats(
        run,
        [
            lazy_map(cohort_output, cohort_gbs_kgd_stats_import)
            for cohort_output in cohort_outputs.values()
        ],
        out_path=os.path.join(gbs_paths.run_root, "gbs_kgd_stats_import.tsv"),
    )

    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return Stage2Output(
        cohorts=cohort_outputs, imported_gbs_kgd_stats=imported_gbs_kgd_stats
    )
