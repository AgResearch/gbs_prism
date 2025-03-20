"""
This module contains tasks for stage 1 of gbs_prism bioinformatics pipeline.
Tasks:
    cook_sample_sheet: Process a raw sample sheet.
    kmer_analysis_one: Run kmer analysis for a single fastq file.
    kmer_analysis_all: Run kmer_analysis_one on all fastq files.
    dedupe_one: Dedupe a single fastq file.
    dedupe_all: Run dedupe_one on all fastq files.
    get_gbs_keyfiles: Get GBS keyfiles.
    get_gbs_targets: Get GBS targets for stage 2.
    run_stage1: Triggers running of the tasks via redun.
Dataclasses:
    CookSampleSheetOutput: Collect the outputs of processed sample sheet.
    BclConvertOutput: Collect the outputs of bclconvert.
    GbsTargetsOutput: Collect targets and paths for gbs_prism stage 2.
    Stage1Output: Collect the outputs of stage 1.
"""

import os.path
from dataclasses import dataclass

from redun import task, File
from typing import Literal

redun_namespace = "agr.gbs_prism"

from agr.redun import one_forall
from agr.redun.cluster_executor import get_tool_config, run_job_1
from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet
from agr.seq.dedupe import (
    dedupe_job_spec,
    remove_dedupe_turds,
    DEDUPE_TOOL_NAME,
)
from agr.gbs_prism.gbs_target_spec import (
    gquery_gbs_target_spec,
    write_gbs_target_spec,
    GbsTargetSpec,
)
from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import SeqPaths, GbsPaths
from agr.redun.tasks import (
    real_or_fake_bcl_convert,
    fastq_sample,
    fastqc,
    kmer_analysis,
    multiqc,
)
from agr.redun.tasks.fastq_sample import FastqSampleSpec


@dataclass
class CookSampleSheetOutput:
    """Dataclass to collect the outputs of processed sample sheet."""

    sample_sheet: File
    illumina_platform_root: str
    paths: SeqPaths
    expected_fastq: set[str]
    gbs_libraries: list[str]


@task()
def cook_sample_sheet(
    sequencer_run: SequencerRun,
    postprocessing_root: str,
    platform: Literal["iseq", "miseq", "novaseq"] = "novaseq",
    impute_lanes=[1, 2],
) -> CookSampleSheetOutput:
    """Process a raw sample sheet into a form compatiable with bclconvert et al."""
    sample_sheet = SampleSheet(
        sequencer_run.sample_sheet_path, impute_lanes=impute_lanes
    )
    # TODO remove the corresponding stuff from Paths class
    illumina_platform_root = os.path.join(postprocessing_root, "illumina", platform)
    illumina_platform_run_root = os.path.join(
        illumina_platform_root, sequencer_run.name
    )
    seq_paths = SeqPaths(illumina_platform_run_root)
    os.makedirs(seq_paths.sample_sheet_dir, exist_ok=True)
    sample_sheet.write(seq_paths.sample_sheet_path)

    return CookSampleSheetOutput(
        sample_sheet=File(seq_paths.sample_sheet_path),
        illumina_platform_root=illumina_platform_root,
        paths=seq_paths,
        expected_fastq=sample_sheet.fastq_files,
        gbs_libraries=sample_sheet.gbs_libraries,
    )


@task()
def dedupe_one(
    fastq_file: File,
    out_dir: str,
) -> File:
    """Dedupe a single fastq file."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(fastq_file.path))

    tool_config = get_tool_config(DEDUPE_TOOL_NAME)
    java_max_heap = tool_config.get("java_max_heap")

    result = run_job_1(
        dedupe_job_spec(
            in_path=fastq_file.path,
            out_path=out_path,
            tmp_dir="/tmp",  # TODO maybe need tmp_dir on large scratch partition
            jvm_args=[f"-Xmx{java_max_heap}"] if java_max_heap is not None else [],
        ),
    )
    remove_dedupe_turds(out_path)
    return result


@task()
def dedupe_all(fastq_files: list[File], out_dir: str) -> list[File]:
    """Dedupe multiple fastq files."""
    return one_forall(dedupe_one, fastq_files, out_dir=out_dir)


@task()
def get_gbs_keyfiles(
    sequencer_run: SequencerRun,
    sample_sheet: File,
    gbs_libraries: list[str],
    deduped_fastq_files: list[File],
    root: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_dir: str,
) -> list[File]:
    """Get GBS keyfiles, which must depend on deduped fastq files having been produced."""
    _ = deduped_fastq_files  # depending on existence rather than value
    gbs_keyfiles = GbsKeyfiles(
        sequencer_run=sequencer_run,
        sample_sheet_path=sample_sheet.path,
        root=root,
        out_dir=out_dir,
        fastq_link_farm=fastq_link_farm,
        backup_dir=backup_dir,
    )
    gbs_keyfiles.create()

    return [
        File(os.path.join(out_dir, "%s.generated.txt" % library))
        for library in gbs_libraries
    ]


@dataclass
class GbsTargetsOutput:
    """Dataclass to collect targets and paths for gbs_prism stage 2."""

    paths: GbsPaths
    spec: GbsTargetSpec
    spec_file: File


@task()
def get_gbs_targets(
    run: str, postprocessing_root: str, fastq_link_farm: str, gbs_keyfiles: list[File]
) -> GbsTargetsOutput:
    """Get GBS target spec, which must depend on GBS keyfiles having been produced."""
    _ = gbs_keyfiles  # depending on existence rather than value
    gbs_root = os.path.join(postprocessing_root, "gbs")
    paths = GbsPaths(root=gbs_root, run=run)
    os.makedirs(paths.run_root, exist_ok=True)
    gbs_target_spec = gquery_gbs_target_spec(run, fastq_link_farm)
    write_gbs_target_spec(paths.target_spec_path, gbs_target_spec)
    return GbsTargetsOutput(
        paths=paths, spec=gbs_target_spec, spec_file=File(paths.target_spec_path)
    )


@dataclass
class Stage1Output:
    """Dataclass to collect the outputs of stage 1."""

    fastqc: list[File]
    multiqc: File
    kmer_analysis: list[File]
    spec: GbsTargetSpec
    spec_file: File
    gbs_paths: GbsPaths


@task()
def run_stage1(
    seq_root: str,
    postprocessing_root: str,
    gbs_backup_dir: str,
    keyfiles_dir: str,
    fastq_link_farm: str,
    run: str,
) -> Stage1Output:
    """Stage 1: bclconvert, fastqc, multiqc, kmer analysis, deduplication, GBS keyfile creation."""
    sequencer_run = SequencerRun(seq_root, run)

    seq = cook_sample_sheet(
        sequencer_run=sequencer_run, postprocessing_root=postprocessing_root
    )

    bclconvert_output = real_or_fake_bcl_convert(
        sequencer_run.dir,
        sample_sheet_path=seq.sample_sheet.path,
        expected_fastq=seq.expected_fastq,
        out_dir=seq.paths.bclconvert_dir,
    )

    fastqc_files = fastqc(bclconvert_output.fastq_files, out_dir=seq.paths.fastqc_dir)

    multiqc_report = multiqc(
        fastqc_files=fastqc_files,
        bclconvert_top_unknowns=bclconvert_output.top_unknown,
        bclconvert_adapter_metrics=bclconvert_output.adapter_metrics,
        bclconvert_demultiplex_stats=bclconvert_output.demultiplexing_metrics,
        bclconvert_quality_metrics=bclconvert_output.quality_metrics,
        bclconvert_run_info_xml=bclconvert_output.run_info_xml,
        out_dir=seq.paths.multiqc_dir,
        run=sequencer_run.name,
    )

    kmer_samples = fastq_sample(
        bclconvert_output.fastq_files,
        spec=FastqSampleSpec(rate=0.0002, minimum_sample_size=10000),
        out_dir=seq.paths.kmer_fastq_sample_dir,
    )

    kmer_analysis_reports = kmer_analysis(
        kmer_samples, out_dir=seq.paths.kmer_analysis_dir
    )

    deduped_fastq = dedupe_all(
        bclconvert_output.fastq_files, out_dir=seq.paths.dedupe_dir
    )

    gbs_keyfiles = get_gbs_keyfiles(
        sequencer_run=sequencer_run,
        sample_sheet=seq.sample_sheet,
        gbs_libraries=seq.gbs_libraries,
        deduped_fastq_files=deduped_fastq,
        root=seq.illumina_platform_root,
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
        fastqc=fastqc_files,
        multiqc=multiqc_report,
        kmer_analysis=kmer_analysis_reports,
        spec=gbs_targets.spec,
        spec_file=gbs_targets.spec_file,
        gbs_paths=gbs_targets.paths,
    )
    # kmer_analysis + is troublesome for now because of in-process problems, but should be fixed and returned
