"""
This module contains tasks for stage 1 of gbs_prism bioinformatics pipeline.
Tasks:
    get_gbs_targets: Get GBS targets for stage 2.
    run_stage1: Triggers running of the tasks via redun.
Dataclasses:
    GbsTargetsOutput: Collect targets and paths for gbs_prism stage 2.
    Stage1Output: Collect the outputs of stage 1.
"""

import os.path
from dataclasses import dataclass

from redun import task, File
from typing import Literal

redun_namespace = "agr.gbs_prism"

from agr.seq.sequencer_run import SequencerRun
from agr.gbs_prism.gbs_target_spec import (
    gquery_gbs_target_spec,
    write_gbs_target_spec,
    GbsTargetSpec,
)
from agr.gbs_prism.paths import SeqPaths, GbsPaths
from agr.redun import JobContext
from agr.redun.tasks import (
    cook_sample_sheet,
    real_or_fake_bcl_convert,
    dedupe_all,
    fastq_sample_all,
    fastqc_all,
    get_gbs_keyfiles,
    kmer_analysis_all,
    multiqc,
)
from agr.redun.tasks.fastq_sample import FastqSampleSpec
from agr.redun.tasks.fastqc import FastqcOutput, fastqc_zip_files
from agr.redun import lazy_map


@dataclass
class GbsTargetsOutput:
    """Dataclass to collect targets and paths for gbs_prism stage 2."""

    paths: GbsPaths
    spec: GbsTargetSpec
    spec_file: File
    gbs_keyfiles: dict[str, File]


@task()
def get_gbs_targets(
    run: str,
    postprocessing_root: str,
    fastq_link_farm: str,
    gbs_keyfiles: dict[str, File],
) -> GbsTargetsOutput:
    """Get GBS target spec, which must depend on GBS keyfiles having been produced."""
    _ = gbs_keyfiles  # depending on existence rather than value
    gbs_root = os.path.join(postprocessing_root, "gbs")
    paths = GbsPaths(root=gbs_root, run=run)
    os.makedirs(paths.run_root, exist_ok=True)
    gbs_target_spec = gquery_gbs_target_spec(run, fastq_link_farm)
    write_gbs_target_spec(paths.target_spec_path, gbs_target_spec)
    return GbsTargetsOutput(
        paths=paths,
        spec=gbs_target_spec,
        spec_file=File(paths.target_spec_path),
        gbs_keyfiles=gbs_keyfiles,
    )


@dataclass
class Stage1Output:
    """Dataclass to collect the outputs of stage 1."""

    sample_sheet: File
    fastqc: list[FastqcOutput]
    multiqc: File
    kmer_analysis: list[File]
    spec: GbsTargetSpec
    spec_file: File
    gbs_paths: GbsPaths
    gbs_keyfiles: dict[str, File]


@task()
def await_run_complete(sequencer_run: SequencerRun) -> File:
    """Await run complete and return the sample sheet as a file, so we retrigger if it changes."""
    sequencer_run.await_complete()

    return File(sequencer_run.sample_sheet_path)


@task()
def run_stage1(
    seq_root: str,
    postprocessing_root: str,
    gbs_backup_dir: str,
    keyfiles_dir: str,
    fastq_link_farm: str,
    run: str,
    job_context: JobContext,
) -> Stage1Output:
    """Stage 1: bclconvert, fastqc, multiqc, kmer analysis, deduplication, GBS keyfile creation."""
    sequencer_run = SequencerRun(seq_root, run)
    platform: Literal["iseq", "miseq", "novaseq"] = "novaseq"
    illumina_platform_root = os.path.join(postprocessing_root, "illumina", platform)
    illumina_platform_run_root = os.path.join(
        illumina_platform_root, sequencer_run.name
    )
    seq_paths = SeqPaths(illumina_platform_run_root)

    raw_sample_sheet = await_run_complete(sequencer_run)

    seq = cook_sample_sheet(
        in_file=raw_sample_sheet,
        out_path=seq_paths.sample_sheet_path,
    )

    bclconvert_output = real_or_fake_bcl_convert(
        sequencer_run.dir,
        sample_sheet_path=seq.sample_sheet.path,
        expected_fastq=seq.expected_fastq,
        out_dir=seq_paths.bclconvert_dir,
        job_context=job_context,
    )

    fastqc_outputs = fastqc_all(
        bclconvert_output.fastq_files,
        out_dir=seq_paths.fastqc_dir,
        job_context=job_context,
    )

    multiqc_report = multiqc(
        fastqc_files=lazy_map(fastqc_outputs, fastqc_zip_files),
        bclconvert_top_unknowns=bclconvert_output.top_unknown,
        bclconvert_adapter_metrics=bclconvert_output.adapter_metrics,
        bclconvert_demultiplex_stats=bclconvert_output.demultiplexing_metrics,
        bclconvert_quality_metrics=bclconvert_output.quality_metrics,
        bclconvert_run_info_xml=bclconvert_output.run_info_xml,
        out_dir=seq_paths.multiqc_dir,
        run=sequencer_run.name,
        job_context=job_context,
    )

    kmer_samples = fastq_sample_all(
        bclconvert_output.fastq_files,
        spec=FastqSampleSpec(rate=0.0002, minimum_sample_size=10000),
        out_dir=seq_paths.kmer_fastq_sample_dir,
        job_context=job_context,
    )

    kmer_analysis_reports = kmer_analysis_all(
        kmer_samples, out_dir=seq_paths.kmer_analysis_dir, job_context=job_context
    )

    deduped_fastq = dedupe_all(
        bclconvert_output.fastq_files,
        out_dir=seq_paths.dedupe_dir,
        job_context=job_context,
    )

    gbs_keyfiles = get_gbs_keyfiles(
        sequencer_run=sequencer_run,
        sample_sheet=seq.sample_sheet,
        gbs_libraries=seq.gbs_libraries,
        deduped_fastq_files=deduped_fastq,
        root=illumina_platform_root,
        out_dir=keyfiles_dir,
        fastq_link_farm=fastq_link_farm,
        backup_dir=gbs_backup_dir,
    )

    gbs_targets = get_gbs_targets(
        run=run,
        postprocessing_root=postprocessing_root,
        fastq_link_farm=fastq_link_farm,
        gbs_keyfiles=gbs_keyfiles,
    )

    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return Stage1Output(
        sample_sheet=seq.sample_sheet,
        fastqc=fastqc_outputs,
        multiqc=multiqc_report,
        kmer_analysis=kmer_analysis_reports,
        spec=gbs_targets.spec,
        spec_file=gbs_targets.spec_file,
        gbs_paths=gbs_targets.paths,
        gbs_keyfiles=gbs_targets.gbs_keyfiles,
    )
