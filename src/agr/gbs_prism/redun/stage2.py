import os.path
from dataclasses import dataclass
from agr.redun.tasks.gupdate import import_gbs_kgd_stats, import_gbs_kgd_cohort_stats
from agr.redun.util import await_results
from redun import task, File
from typing import Optional

redun_namespace = "agr.gbs_prism"

from agr.util.legacy import sanitised_realpath
from agr.util.path import symlink
from agr.redun import concat, lazy_map

from agr.gbs_prism.paths import GbsPaths
from agr.gbs_prism.gbs_target_spec import CohortTargetSpec, GbsTargetSpec
from agr.seq.types import flowcell_id, Cohort
from agr.redun import JobContext
from agr.redun.tasks import (
    bam_stats_all,
    bwa_aln_all,
    bwa_samse_all,
    collate_tags_reads,
    collate_tags_reads_kgdstats,
    cutadapt_all,
    demultiplex,
    fastq_sample_all,
    get_keyfile_for_tassel,
    get_keyfile_for_gbsx,
    gusbase,
    kgd,
    import_gbs_read_tag_counts,
    create_cohort_gbs_kgd_stats_import,
)
from agr.redun.tasks.bwa import Bwa
from agr.redun.tasks.fastq_sample import FastqSampleSpec
from agr.redun.tasks.tassel3 import (
    fastq_name_for_tassel3,
    hap_map_dir,
)
from agr.redun.tasks.kgd import KgdOutput, kgd_dir
from agr.redun.tasks.unblind import (
    get_unblind_script,
    unblind_one,
    unblind_optional,
    unblind_all,
    unblind_each,
)
from agr.gbs_prism.redun.reports.kgd import create_kgd_report, KgdTargets


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
                        spec.cohort.libname, flowcell_id(spec.run), fastq_basename
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
def bwa_all_reference_genomes(
    fastq_files: list[File], spec: CohortSpec, job_context: JobContext
) -> list[File]:
    """bwa_aln and bwa_samse for each file for each of the reference genomes."""
    out_dir = spec.paths.bwa_mapping_dir(spec.cohort.name)
    os.makedirs(out_dir, exist_ok=True)
    out_paths = []
    for ref_name, ref_path in spec.target.alignment_references.items():
        job_context_ref = job_context.with_sub(ref_name)
        alns = bwa_aln_all(
            fastq_files,
            ref_name=ref_name,
            ref_path=ref_path,
            bwa=spec.bwa,
            out_dir=out_dir,
            job_context=job_context_ref,
        )
        bam_files = bwa_samse_all(alns, ref_path=ref_path, job_context=job_context_ref)
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
    # this is usually a dict of length 1 whose key is the cohort name,
    # except if there were multiple parts, in which case the keys are
    # a composite of cohort name and part.
    fastq_to_tag_count_stdout: dict[str, File]
    collated_tag_count: File
    kgd_output: KgdOutput
    gbs_kgd_stats_import: Optional[File]
    collated_kgd_stats: Optional[File]
    collated_kgd_stats_unblind: Optional[File]
    gusbase_comet: Optional[File]
    tag_count_unblind: File
    hap_map_files_unblind: list[File]
    kgd_text_files_unblind: dict[str, File]
    kgd_stdout_unblind: Optional[File]
    kgd_report: Optional[File]


@dataclass
class CohortImport:
    imported_gbs_kgd_cohort_stats: Optional[File]


def _collated_tag_count(cohort_output: CohortOutput) -> Optional[File]:
    return cohort_output.collated_tag_count


def _kgd_stdout(cohort_output: CohortOutput) -> Optional[File]:
    return cohort_output.kgd_output.kgd_stdout


def _cohort_gbs_kgd_stats_import(cohort_output: CohortOutput) -> Optional[File]:
    return cohort_output.gbs_kgd_stats_import


@task()
def run_cohort(
    spec: CohortSpec, gbs_keyfile: File, job_context: JobContext
) -> CohortOutput:
    """Run the entire pipeline for a single cohort."""
    job_context = job_context.with_sub(spec.cohort.name)

    fastq_links, munged_fastq_links_for_tassel = create_cohort_fastq_links(spec)

    bwa_sampled = fastq_sample_all(
        fastq_links,
        spec=spec.bwa_sample,
        out_dir=spec.paths.bwa_mapping_dir(spec.cohort.name),
        job_context=job_context,
    )

    trimmed = cutadapt_all(
        bwa_sampled,
        out_dir=spec.paths.bwa_mapping_dir(spec.cohort.name),
        job_context=job_context,
    )

    bam_files = bwa_all_reference_genomes(trimmed, spec, job_context=job_context)
    bam_stats_files = bam_stats_all(bam_files)

    keyfile_for_tassel = get_keyfile_for_tassel(
        spec.paths.run_root, spec.run, spec.cohort, gbs_keyfile
    )
    keyfile_for_gbsx = get_keyfile_for_gbsx(
        spec.paths.run_root, spec.run, spec.cohort, gbs_keyfile
    )

    cohort_dir = spec.paths.cohort_dir(spec.cohort.name)
    cohort_blind_dir = spec.paths.cohort_blind_dir(spec.cohort.name)

    unblind_script = get_unblind_script(
        cohort_blind_dir,
        flowcell_id(spec.run),
        spec.cohort.enzyme,
        spec.cohort.gbs_cohort,
        spec.cohort.libname,
        keyfile_for_tassel,
    )

    demultiplexed = demultiplex(
        work_dir=cohort_blind_dir,
        enzyme=spec.cohort.enzyme,
        keyfile=keyfile_for_tassel,
        job_context=job_context,
        prefix=spec.cohort.name,
    )
    tag_count = demultiplexed.tag_count
    collated_tag_count = collate_tags_reads(
        run=spec.run,
        cohort=spec.cohort.name,
        tag_counts=tag_count,
        out_path=os.path.join(cohort_blind_dir, "CollatedTagCount.tsv"),
    )

    unblind_script = get_unblind_script(
        spec.paths.cohort_blind_dir(spec.cohort.name),
        flowcell_id(spec.run),
        spec.cohort.enzyme,
        spec.cohort.gbs_cohort,
        spec.cohort.libname,
        keyfile_for_tassel,
    )

    tag_count_unblind = unblind_one(
        tag_count, unblind_script, spec.paths.cohort_dir(spec.cohort.name)
    )

    hap_map_files_unblind = unblind_all(
        demultiplexed.hap_map_files,
        unblind_script,
        hap_map_dir(cohort_dir),
    )

    kgd_output = kgd(
        work_dir=cohort_blind_dir,
        hap_map_files=demultiplexed.hap_map_files,
        job_context=job_context,
        genotyping_method=spec.target.genotyping_method,
    )

    collated_kgd_stats = collate_tags_reads_kgdstats(
        run=spec.run,
        cohort=spec.cohort.name,
        tag_counts=tag_count,
        kgd_stats=kgd_output.sample_stats_csv,
        keyfile_for_tassel=keyfile_for_tassel,
        out_path=os.path.join(cohort_blind_dir, "TagCountsAndSampleStats.csv"),
    )
    collated_kgd_stats_unblind = unblind_optional(
        collated_kgd_stats, unblind_script=unblind_script, out_dir=cohort_dir
    )

    gbs_kgd_stats_import = create_cohort_gbs_kgd_stats_import(
        run=spec.run,
        cohort_name=spec.cohort.name,
        kgd_stats_csv=kgd_output.sample_stats_csv,
    )

    gusbase_comet = gusbase(kgd_output.gusbase_rdata, job_context=job_context)

    kgd_text_files_unblind = unblind_each(
        kgd_output.text_files,
        unblind_script,
        kgd_dir(cohort_dir),
    )
    kgd_stdout_unblind = unblind_optional(
        kgd_output.kgd_stdout, unblind_script, cohort_dir
    )

    kgd_report = create_kgd_report(
        title=spec.cohort.name,
        cohorts_targets={
            spec.cohort.name: KgdTargets(
                kgd_output=kgd_output,
                kgd_text_files_unblind=kgd_text_files_unblind,
                hap_map_files_unblind=hap_map_files_unblind,
            )
        },
        out_path=os.path.join(cohort_dir, "KGD.html"),
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
        fastq_to_tag_count_stdout=demultiplexed.fastq_to_tag_count_stdout,
        collated_tag_count=collated_tag_count,
        kgd_output=kgd_output,
        gbs_kgd_stats_import=gbs_kgd_stats_import,
        collated_kgd_stats=collated_kgd_stats,
        collated_kgd_stats_unblind=collated_kgd_stats_unblind,
        gusbase_comet=gusbase_comet,
        tag_count_unblind=tag_count_unblind,
        hap_map_files_unblind=hap_map_files_unblind,
        kgd_text_files_unblind=kgd_text_files_unblind,
        kgd_stdout_unblind=kgd_stdout_unblind,
        kgd_report=kgd_report,
    )
    return output


@dataclass
class Stage2Output:
    cohorts: dict[str, CohortOutput]
    imported_gbs_kgd_stats: File
    imported_collated_tag_counts: File
    cohort_imports: dict[str, CohortImport]


@task()
def run_stage2(
    run: str,
    spec: GbsTargetSpec,
    gbs_paths: GbsPaths,
    gbs_keyfiles: dict[str, File],
    job_context: JobContext,
) -> Stage2Output:
    cohort_outputs = {}
    cohorts = {cohort_name: Cohort.parse(cohort_name) for cohort_name in spec.cohorts}

    bwa_sample = FastqSampleSpec(
        rate=0.00005,
        minimum_sample_size=150000,
    )

    bwa = Bwa(barcode_len=10)

    for name, target in spec.cohorts.items():
        cohort = cohorts[name]
        target = CohortSpec(
            run=run,
            cohort=cohort,
            target=target,
            paths=gbs_paths,
            bwa_sample=bwa_sample,
            bwa=bwa,
        )

        cohort_outputs[name] = run_cohort(
            target, gbs_keyfiles[cohort.libname], job_context
        )

    # this import step need to be once for all cohorts
    imported_collated_tag_counts = import_gbs_read_tag_counts(
        run=run,
        collated_tag_counts=[
            lazy_map(cohort_output, _collated_tag_count)
            for cohort_output in cohort_outputs.values()
        ],
        out_path=os.path.join(gbs_paths.run_root, "ImportedCollatedTagCounts.tsv"),
    )

    # as does this, which we must run after the other, according to this comment buried deep inside gquery 😬
    #
    # These two partial updates should always be run together, in the order import_gbs_read_tag_counts, then import_gbs_kgd_stats
    imported_gbs_kgd_stats = import_gbs_kgd_stats(
        ready=await_results(imported_collated_tag_counts),
        run=run,
        cohort_imports=[
            lazy_map(cohort_output, _cohort_gbs_kgd_stats_import)
            for cohort_output in cohort_outputs.values()
        ],
        out_path=os.path.join(gbs_paths.run_root, "gbs_kgd_stats_import.tsv"),
    )

    # and this import step is done for each cohort separately
    cohort_imports = {}
    for name, target in spec.cohorts.items():
        imported_gbs_kgd_cohort_stats = import_gbs_kgd_cohort_stats(
            run, cohorts[name], lazy_map(cohort_outputs[name], _kgd_stdout)
        )
        cohort_imports[name] = CohortImport(
            imported_gbs_kgd_cohort_stats=imported_gbs_kgd_cohort_stats
        )

    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return Stage2Output(
        cohorts=cohort_outputs,
        imported_gbs_kgd_stats=imported_gbs_kgd_stats,
        imported_collated_tag_counts=imported_collated_tag_counts,
        cohort_imports=cohort_imports,
    )
