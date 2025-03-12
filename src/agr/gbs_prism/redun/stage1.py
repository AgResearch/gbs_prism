"""
This module contains tasks for stage 1 of gbs_prism bioinformatics pipeline.
Tasks:
    cook_sample_sheet: Process a raw sample sheet.
    bclconvert: Run bclconvert and return fastq files and summary metrics.
    fastqc_one: Run fastqc on a single fastq file, returning  .zip results.
    fastqc_all: Run fastqc on multiple files, returning list of .zip results.
    multiqc_report: Run MultiQC .html aggregating FastQC and BCLConvert reports.
    kmer_sample_one: Sample a single fastq file as required for kmer analysis.
    kmer_sample_all: Sample all fastq files as required for kmer analysis.
    kmer_analysis_one: Run kmer analysis for a single fastq file.
    kmer_analysis_all: Run kmer analysis for multiple fastq files.
    dedupe_one: Dedupe a single fastq file.
    dedupe_all: Dedupe multiple fastq files.
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
from redun.context import get_context
from typing import List, Literal, Set

redun_namespace = "agr.gbs_prism"

from agr.redun import one_forall, all_forall
from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet

# Fake bcl-convert may be selected in context
# from agr.seq.bclconvert import BclConvert
from agr.fake.bclconvert import create_real_or_fake_bcl_convert
from agr.seq.dedupe import dedupe
from agr.seq.fastqc import fastqc
from agr.seq.multiqc import multiqc
from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.gbs_target_spec import (
    gquery_gbs_target_spec,
    write_gbs_target_spec,
    GbsTargetSpec,
)
from agr.gbs_prism.kmer_analysis import run_kmer_analysis
from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import SeqPaths, GbsPaths


@dataclass
class CookSampleSheetOutput:
    """Dataclass to collect the outputs of processed sample sheet."""
    sample_sheet: File
    illumina_platform_root: str
    paths: SeqPaths
    expected_fastq: Set[str]
    gbs_libraries: List[str]


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


@dataclass
class BclConvertOutput:
    """Dataclass to collect the outputs of bclconvert."""
    fastq_files: List[File]
    adapter_metrics: File
    demultiplexing_metrics: File
    quality_metrics: File
    run_info_xml: File
    top_unknown: File


@task()
def bclconvert(
    in_dir: str,
    sample_sheet_path: str,
    expected_fastq: Set[str],
    out_dir: str,
    bcl_convert_context=get_context("tools.bcl_convert"),
) -> BclConvertOutput:
    """Run bclconvert and return fastq files and metrics."""
    os.makedirs(out_dir, exist_ok=True)
    bclconvert = create_real_or_fake_bcl_convert(
        in_dir=in_dir,
        sample_sheet_path=sample_sheet_path,
        out_dir=out_dir,
        bcl_convert_context=bcl_convert_context,
    )
    bclconvert.run()
    bclconvert.check_expected_fastq_files(expected_fastq)
    return BclConvertOutput(
        fastq_files=[
            File(os.path.join(out_dir, fastq_file)) for fastq_file in expected_fastq
        ],
        adapter_metrics=File(bclconvert.adapter_metrics_path),
        demultiplexing_metrics=File(bclconvert.demultiplex_stats_path),
        quality_metrics=File(bclconvert.quality_metrics_path),
        run_info_xml=File(bclconvert.run_info_xml_path),
        top_unknown=File(bclconvert.top_unknown_path),
    )


@task()
def fastqc_one(fastq_file: File, out_dir: str) -> File:
    """Run fastqc on a single file, returning a list of the zip results."""
    fastqc(in_path=fastq_file.path, out_dir=out_dir)
    report = fastq_file.path.removesuffix(".gz").removesuffix(".fastq") + "_fastqc.zip"
    return File(report)


@task()
def fastqc_all(fastq_files: List[File], out_dir: str) -> List[File]:
    """Run fastqc on multiple files, returning concatenation of all the zip results."""
    return one_forall(fastqc_one, fastq_files, out_dir=out_dir)


@task()
def multiqc_report(
    fastqc_files: List[File],
    bclconvert_top_unknowns: File,
    bclconvert_adapter_metrics: File,
    bclconvert_demultiplex_stats: File,
    bclconvert_quality_metrics: File,
    bclconvert_run_info_xml: File,
    out_dir: str,
    run: str,
) -> File:
    """Run MultiQC aggregating FastQC and BCLConvert reports."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s_multiqc_report.html" % run)
    multiqc(
        [fastqc_file.path for fastqc_file in fastqc_files],
        bclconvert_top_unknowns.path,
        bclconvert_adapter_metrics.path,
        bclconvert_demultiplex_stats.path,
        bclconvert_quality_metrics.path,
        bclconvert_run_info_xml.path,
        out_dir,
        out_path,
    )
    return File(out_path)


@task()
def kmer_sample_one(fastq_file: File, out_dir: str) -> File:
    """Sample a single fastq file as required for kmer analysis."""
    os.makedirs(out_dir, exist_ok=True)
    kmer_sample = FastqSample(sample_rate=0.0002, minimum_sample_size=10000)
    # the ugly name is copied from legacy gbs_prism
    out_path = os.path.join(
        out_dir,
        "%s.fastq.%s.fastq" % (os.path.basename(fastq_file.path), kmer_sample.moniker),
    )
    kmer_sample.run(in_path=fastq_file.path, out_path=out_path)
    return File(out_path)


@task()
def kmer_sample_all(fastq_files: List[File], out_dir: str) -> List[File]:
    """Sample all fastq files as required for kmer analysis."""
    return one_forall(kmer_sample_one, fastq_files, out_dir=out_dir)


@task()
def kmer_analysis_one(fastq_file: File, out_dir: str) -> File:
    """Run kmer analysis for a single fastq file."""
    os.makedirs(out_dir, exist_ok=True)
    kmer_size = 6
    out_path = os.path.join(
        out_dir,
        "%s.k%d.1" % (os.path.basename(fastq_file.path), kmer_size),
    )
    run_kmer_analysis(
        in_path=fastq_file.path,
        out_path=out_path,
        input_filetype="fasta",
        kmer_size=kmer_size,
        # this causes it to crash: 😩
        # assemble_low_entropy_kmers=True
    )
    return File(out_path)


@task()
def kmer_analysis_all(fastq_files: List[File], out_dir: str) -> List[File]:
    """Run kmer analysis for multiple fastq files."""
    return one_forall(kmer_analysis_one, fastq_files, out_dir=out_dir)


@task()
def dedupe_one(
    fastq_file: File,
    out_dir: str,
    java_max_heap=get_context("tools.dedupe.java_max_heap"),
) -> File:
    """Dedupe a single fastq file."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(fastq_file.path))
    dedupe(
        in_path=fastq_file.path,
        out_path=out_path,
        tmp_dir="/tmp",  #TODO maybe need tmp_dir on large scratch partition
        jvm_args=[f"-Xmx{java_max_heap}"] if java_max_heap is not None else [],
    )
    return File(out_path)


@task()
def dedupe_all(fastq_files: List[File], out_dir: str) -> List[File]:
    """Dedupe multiple fastq files."""
    return one_forall(dedupe_one, fastq_files, out_dir=out_dir)


@task()
def get_gbs_keyfiles(
    sequencer_run: SequencerRun,
    sample_sheet: File,
    gbs_libraries: List[str],
    deduped_fastq_files: List[File],
    root: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_dir: str,
) -> List[File]:
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


@task()
def get_gbs_targets(
    run: str, postprocessing_root: str, fastq_link_farm: str, gbs_keyfiles: List[File]
) -> GbsTargetsOutput:
    """Get GBS target spec, which must depend on GBS keyfiles having been produced."""
    _ = gbs_keyfiles  # depending on existence rather than value
    gbs_root = os.path.join(postprocessing_root, "gbs")
    paths = GbsPaths(root=gbs_root, run=run)
    os.makedirs(paths.run_root, exist_ok=True)
    gbs_target_spec = gquery_gbs_target_spec(run, fastq_link_farm)
    write_gbs_target_spec(paths.target_spec_path, gbs_target_spec)
    return GbsTargetsOutput(paths=paths, spec=gbs_target_spec)


@dataclass
class Stage1Output:
    """Dataclass to collect the outputs of stage 1."""
    fastqc: List[File]
    multiqc: File
    kmer_analysis: List[File]
    spec: GbsTargetSpec
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

    bclconvert_output = bclconvert(
        sequencer_run.dir,
        sample_sheet_path=seq.sample_sheet.path,
        expected_fastq=seq.expected_fastq,
        out_dir=seq.paths.bclconvert_dir,
    )

    fastqc_files = fastqc_all(
        bclconvert_output.fastq_files, out_dir=seq.paths.fastqc_dir
    )

    multiqc_report_out = multiqc_report(
        fastqc_files=fastqc_files,
        bclconvert_top_unknowns=bclconvert_output.top_unknown,
        bclconvert_adapter_metrics=bclconvert_output.adapter_metrics,
        bclconvert_demultiplex_stats=bclconvert_output.demultiplexing_metrics,
        bclconvert_quality_metrics=bclconvert_output.quality_metrics,
        bclconvert_run_info_xml=bclconvert_output.run_info_xml,
        out_dir=seq.paths.multiqc_dir,
        run=sequencer_run.name,
    )

    kmer_samples = kmer_sample_all(
        bclconvert_output.fastq_files, out_dir=seq.paths.kmer_fastq_sample_dir
    )

    kmer_analysis = kmer_analysis_all(kmer_samples, out_dir=seq.paths.kmer_analysis_dir)

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
        multiqc=multiqc_report_out,
        kmer_analysis=kmer_analysis,
        spec=gbs_targets.spec,
        gbs_paths=gbs_targets.paths,
    )
    # kmer_analysis + is troublesome for now because of in-process problems, but should be fixed and returned
