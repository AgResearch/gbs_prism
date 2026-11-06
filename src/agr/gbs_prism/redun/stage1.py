"""
This module contains tasks for stage 1 of gbs_prism bioinformatics pipeline.
Tasks:
    get_gbs_targets: Get GBS targets for stage 2.
    split_barcodes_run: Pre-flight checks and splitBarcode demultiplexing per lane.
    run_stage1: Triggers running of the tasks via redun.
Dataclasses:
    GbsTargetsOutput: Collect targets and paths for gbs_prism stage 2.
    Stage1Output: Collect the outputs of stage 1.
"""

import os.path
from dataclasses import dataclass

from redun import task, File
from redun_psij import JobContext

redun_namespace = "agr.gbs_prism"

from agr.seq.sequencer_run import SequencerRun
from agr.seq.mgi.barcodes import lane_plan, write_barcode_file
from agr.seq.mgi.sample_sheet import (
    GENERATE_KEYFILE_SECTION,
    MgiSampleSheet,
    data_rows,
    gbs_library_specs,
    lane_number,
    lanes_by_library,
    lanes_in_sample_sheet,
    read_sample_sheet,
    without_sections,
)
from agr.gbs_prism.gbs_target_spec import (
    gquery_gbs_target_spec,
    write_gbs_target_spec,
    GbsTargetSpec,
)
from agr.gbs_prism.paths import Paths, GbsPaths
from agr.redun.tasks import (
    archive_sample_sheet,
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

# Lane fastqs must be unchanged across this interval before anything reads them; a
# copy with nothing written for this long is stalled and stops the run.
FASTQ_STABLE_INTERVAL_S = 5 * 60
# Backstop: give up if a still-progressing copy has not finished by then. A slow copy
# (DL100022099 L02/L04 re-copy, 6 Nov: ~1.6 MB/s, ~7 h) must fit, so a run can be
# launched ahead of it and start by itself when it completes.
FASTQ_STABLE_MAX_WAIT_S = 24 * 60 * 60


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
    """Get GBS target spec, which must depend on GBS keyfiles having been produced.

    The spec includes the keyfile-indicated reference genomes per cohort, for the
    mapping % summary in the report.
    """
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
def split_barcodes_run(
    seq_root: str,
    run: str,
    demux_sheet: MgiSampleSheet,
    postprocessing_root: str,
    job_context: JobContext,
) -> dict[int, SplitBarcodesOutput]:
    """Pre-flight checks, then splitBarcode demultiplexing of every lane.

    `demux_sheet` is the parsed sheet *without* `[GenerateKeyfile]`, and redun hashes
    it by value. An edit confined to `[GenerateKeyfile]` therefore makes this a cache
    hit: no stability wait, no fastq scan, no re-demultiplexing. Any other edit
    re-runs this body. Each lane's `split_barcodes_one` then re-runs only if that
    lane's barcode file or `-b` arguments actually changed, because
    `write_barcode_file` leaves an unchanged file's mtime alone.

    Everything derivable from the sample sheet - the lane set, the barcode geometry
    and the `-b` arguments - is resolved **here**, before any Slurm job is submitted.
    That follows `mgi_prism`, where a mismatched sheet/run pair aborts at DAG-build
    time rather than after a long demultiplexing job has quietly sent a whole lane to
    `undecoded`.

    The fastqs are vetted first, also before any Slurm job: present, stable, finished
    gzip copies, and md5-identical to the instrument's `FileInfo.txt` (about 1.5 min
    for 4 lanes, in parallel on this host). A run may be launched ahead of its copy:
    this waits up to 24 h while the copy progresses and stops at once if it stalls.
    """
    sequencer_run = SequencerRun(seq_root, run)
    paths = Paths(postprocessing_root=postprocessing_root, run=run)

    lanes = [lane_number(label) for label in lanes_in_sample_sheet(demux_sheet)]
    libraries = sorted(lanes_by_library(demux_sheet))

    # Fail fast and legibly if a lane's fastqs are absent altogether, then wait for
    # them to stop changing and look like finished gzip copies: they arrive by an SMB
    # copy that may still be running, and `lane_plan` below is the first thing to read
    # them. Finally check every fastq's md5 against the instrument's FileInfo.txt, the
    # only check a copy that stalled or was rewritten cannot pass.
    sequencer_run.validate(lanes=lanes)
    sequencer_run.wait_until_stable(
        lanes=lanes,
        interval_s=FASTQ_STABLE_INTERVAL_S,
        max_wait_s=FASTQ_STABLE_MAX_WAIT_S,
    )
    sequencer_run.verify_checksums(lanes=lanes)
    paths.make_run_dirs(lanes=lanes, libraries=libraries)

    # Barcode geometry per lane, confirmed against that lane's own reads. Raises
    # rather than guessing - a wrong offset yields a run that looks successful while
    # sending ~100% of reads to `undecoded`.
    lane_plans = {
        lane: lane_plan(demux_sheet, lane, sequencer_run.dir, run) for lane in lanes
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

    return {
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


@task()
def run_stage1(
    seq_root: str,
    sample_sheet: File,
    postprocessing_root: str,
    gbs_backup_dir: str,
    keyfiles_dir: str,
    fastq_link_farm: str,
    run: str,
    job_context: JobContext,
) -> Stage1Output:
    """Stage 1: splitBarcode demultiplexing, fastqc, multiqc, kmer analysis, lane
    merging, GBS keyfile creation.

    `sample_sheet` is a `File` (from `get_sample_sheet`), so any edit to the sheet,
    even a `touch`, re-runs this body. The body only parses the sheet, which is
    cheap, and splits it into value keys, so each child re-runs only for the edits
    that concern it:

    - `without_sections(sheet, [GenerateKeyfile])` keys `split_barcodes_run`.
      A `[GenerateKeyfile]`-only edit leaves demultiplexing and QC cached.
    - `gbs_library_specs(sheet)` keys each library's keyfile import, so a
      `[GenerateKeyfile]` edit re-imports only the libraries whose rows changed.
    - `data_rows(sheet)` is a key shared by every library's import, so any
      `[Data]` edit re-imports them all.
    """
    paths = Paths(postprocessing_root=postprocessing_root, run=run)

    # The MGI sheet lives outside the run tree, and gquery cross-checks its
    # [Header] Flowcell against this filename stem, so the two must agree.
    sample_sheet_path = sample_sheet.path
    sheet = read_sample_sheet(sample_sheet_path)

    library_lanes = lanes_by_library(sheet)
    libraries = sorted(library_lanes)

    # Archive the sheet actually processed. It lives outside the run tree and can be
    # edited afterwards, so without this the run has no record of what it read - and
    # the report's relative link would climb out of the postprocessing tree.
    archived_sample_sheet = archive_sample_sheet(
        sample_sheet, paths.seq.archived_sample_sheet(run)
    )

    demultiplexed = split_barcodes_run(
        seq_root=seq_root,
        run=run,
        demux_sheet=without_sections(sheet, [GENERATE_KEYFILE_SECTION]),
        postprocessing_root=postprocessing_root,
        job_context=job_context,
    )

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
        run=run,
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
        data_rows=data_rows(sheet),
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
        sample_sheet=archived_sample_sheet,
        fastqc=fastqc_outputs,
        multiqc=multiqc_report,
        kmer_analysis=kmer_analysis_reports,
        merged_fastq=merged_fastq,
        spec=gbs_targets.spec,
        spec_file=gbs_targets.spec_file,
        gbs_paths=gbs_targets.paths,
        gbs_keyfiles=gbs_targets.gbs_keyfiles,
    )
