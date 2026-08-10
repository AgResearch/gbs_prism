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
import shutil
from dataclasses import dataclass

from redun import task, File
from redun_psij import JobContext

redun_namespace = "agr.gbs_prism"

from agr.seq.sequencer_run import SequencerRun
from agr.seq.mgi.barcodes import lane_plan, write_barcode_file
from agr.seq.mgi.sample_sheet import (
    gbs_library_specs,
    lane_number,
    lanes_by_library,
    lanes_in_sample_sheet,
    read_sample_sheet,
)
from agr.gbs_prism.gbs_target_spec import (
    gquery_gbs_target_spec,
    write_gbs_target_spec,
    GbsTargetSpec,
)
from agr.gbs_prism.paths import Paths, GbsPaths
from agr.redun.tasks import (
    barcode_stat_multiqc,
    fastq_sample_all,
    fastqc_all,
    get_gbs_keyfiles,
    kmer_analysis_all,
    merge_all_libraries,
    multiqc,
    split_barcodes_one,
)
from agr.redun.tasks.fastq_sample import FastqSampleSpec
from agr.redun.tasks.fastqc import FastqcOutput, fastqc_zip_files
from agr.redun.tasks.split_barcodes import SplitBarcodesOutput
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
    merged_fastq: dict[str, File]
    spec: GbsTargetSpec
    spec_file: File
    gbs_paths: GbsPaths
    gbs_keyfiles: dict[str, File]


def _all_fastq(demultiplexed: dict[int, SplitBarcodesOutput]) -> list[File]:
    """Every demultiplexed fastq across every lane, for the per-file QC tasks."""
    return [
        fastq_file
        for lane in sorted(demultiplexed)
        for fastq_file in demultiplexed[lane].fastq_files
    ]


def _fastq_by_lane(
    demultiplexed: dict[int, SplitBarcodesOutput],
) -> dict[int, list[File]]:
    return {lane: output.fastq_files for lane, output in demultiplexed.items()}


def _barcode_stats(demultiplexed: dict[int, SplitBarcodesOutput]) -> dict[str, File]:
    """Lane *label* -> BarcodeStat.txt, for the MultiQC custom content.

    Keyed by label so no lane name is ever inferred from a path.
    """
    return {output.lane: output.barcode_stat for output in demultiplexed.values()}


def _barcode_stats_by_lane(
    demultiplexed: dict[int, SplitBarcodesOutput],
) -> dict[int, File]:
    """Lane *number* -> BarcodeStat.txt, for the merge policy's read counts."""
    return {lane: output.barcode_stat for lane, output in demultiplexed.items()}


@task()
def run_stage1(
    seq_root: str,
    sample_sheet_root: str,
    postprocessing_root: str,
    gbs_backup_dir: str,
    keyfiles_dir: str,
    fastq_link_farm: str,
    run: str,
    job_context: JobContext,
) -> Stage1Output:
    """Stage 1: splitBarcode demultiplexing, fastqc, multiqc, kmer analysis, lane
    merging, GBS keyfile creation.

    Everything derivable from the sample sheet - the lane set, the lane->library map,
    the barcode geometry and the `-b` arguments - is resolved **here**, in the
    composing task, before any Slurm job is submitted. That follows `mgi_prism`,
    where a mismatched sheet/run pair aborts at DAG-build time rather than after a
    long demultiplexing job has quietly sent a whole lane to `undecoded`.
    """
    sequencer_run = SequencerRun(seq_root, run)
    paths = Paths(postprocessing_root=postprocessing_root, run=run)

    # The MGI sheet lives outside the run tree, and gquery cross-checks its
    # [Header] Flowcell against this filename stem, so the two must agree.
    sample_sheet_path = os.path.join(sample_sheet_root, "%s.csv" % run)
    sheet = read_sample_sheet(sample_sheet_path)

    lanes = [lane_number(label) for label in lanes_in_sample_sheet(sheet)]
    library_lanes = lanes_by_library(sheet)
    libraries = sorted(library_lanes)

    # The run is required to have finished before the pipeline is launched; this only
    # fails fast and legibly if it has not.
    sequencer_run.validate(lanes=lanes)
    paths.make_run_dirs(lanes=lanes, libraries=libraries)

    # Archive the sheet actually processed. It lives outside the run tree and can be
    # edited afterwards, so without this the run has no record of what it read - and
    # the report's relative link would climb out of the postprocessing tree.
    archived_sample_sheet = paths.seq.archived_sample_sheet(run)
    _ = shutil.copyfile(sample_sheet_path, archived_sample_sheet)

    # Barcode geometry per lane, confirmed against that lane's own reads. Raises
    # rather than guessing - a wrong offset yields a run that looks successful while
    # sending ~100% of reads to `undecoded`.
    lane_plans = {
        lane: lane_plan(sheet, lane, sequencer_run.dir, run) for lane in lanes
    }
    barcode_files = {
        lane: File(
            write_barcode_file(
                plan.entries,
                os.path.join(
                    paths.seq.barcodes_dir, "%s.%s.barcodes" % (run, plan.lane)
                ),
            )
        )
        for lane, plan in lane_plans.items()
    }

    demultiplexed = {
        lane: split_barcodes_one(
            lane=plan.lane,
            read_args=plan.reads.cli_args,
            barcode_file=barcode_files[lane],
            b_args=plan.b_args,
            out_dir=paths.seq.demux_dir(lane),
            job_context=job_context,
        )
        for lane, plan in lane_plans.items()
    }

    all_fastq = lazy_map(demultiplexed, _all_fastq)

    fastqc_outputs = fastqc_all(
        all_fastq,
        out_dir=paths.seq.fastqc_dir,
        job_context=job_context,
    )

    demux_custom_content = barcode_stat_multiqc(
        run=run,
        barcode_stats=lazy_map(demultiplexed, _barcode_stats),
        out_dir=paths.seq.multiqc_custom_dir,
    )

    multiqc_report = multiqc(
        fastqc_files=lazy_map(fastqc_outputs, fastqc_zip_files),
        custom_content=demux_custom_content,
        out_dir=paths.seq.multiqc_dir,
        run=sequencer_run.name,
        job_context=job_context,
    )

    kmer_samples = fastq_sample_all(
        all_fastq,
        spec=FastqSampleSpec(rate=0.0002, minimum_sample_size=10000),
        out_dir=paths.seq.kmer_fastq_sample_dir,
        job_context=job_context,
    )

    kmer_analysis_reports = kmer_analysis_all(
        kmer_samples, out_dir=paths.seq.kmer_analysis_dir, job_context=job_context
    )

    merged_fastq = merge_all_libraries(
        demultiplexed=lazy_map(demultiplexed, _fastq_by_lane),
        # BarcodeStat.txt reports per-library read counts exactly, so the merge
        # policy's threshold is checked without reading a fastq.
        barcode_stats=lazy_map(demultiplexed, _barcode_stats_by_lane),
        lanes_by_library=library_lanes,
        merged_paths={
            library: paths.seq.merged_fastq(library, run) for library in libraries
        },
        job_context=job_context,
    )

    gbs_keyfiles = get_gbs_keyfiles(
        sample_sheet_path=sample_sheet_path,
        library_specs=gbs_library_specs(sheet),
        merged_fastq=merged_fastq,
        merged_fastq_dirs={
            library: paths.seq.merged_dir(library) for library in libraries
        },
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
        sample_sheet=File(archived_sample_sheet),
        fastqc=fastqc_outputs,
        multiqc=multiqc_report,
        kmer_analysis=kmer_analysis_reports,
        merged_fastq=merged_fastq,
        spec=gbs_targets.spec,
        spec_file=gbs_targets.spec_file,
        gbs_paths=gbs_targets.paths,
        gbs_keyfiles=gbs_targets.gbs_keyfiles,
    )
