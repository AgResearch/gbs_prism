import os.path
from dataclasses import dataclass

from redun import task, File
from redun.context import get_context
from typing import List, Literal, Set

redun_namespace = "agr.gbs_prism"

from agr.redun import one_forall
from agr.redun.cluster_executor import get_tool_config, run_job_1, run_job_n
from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet

# Fake bcl-convert may be selected in context
from agr.seq.bclconvert import BCLCONVERT_JOB_FASTQ, BclConvertError
from agr.fake.bclconvert import FakeBclConvert, create_real_or_fake_bcl_convert
from agr.seq.dedupe import (
    dedupe_job_spec,
    remove_dedupe_turds,
    DEDUPE_TOOL_NAME,
)
from agr.seq.fastqc import fastqc_job_spec
from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.gbs_target_spec import (
    gquery_gbs_target_spec,
    write_gbs_target_spec,
    GbsTargetSpec,
)
from agr.gbs_prism.kmer_analysis import kmer_analysis_job_spec
from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import SeqPaths, GbsPaths
from agr.gbs_prism import EXECUTOR_CONFIG_PATH_ENV

from agr.util.path import remove_if_exists


@dataclass
class CookSampleSheetOutput:
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


@task()
def bclconvert(
    in_dir: str,
    sample_sheet_path: str,
    expected_fastq: Set[str],
    out_dir: str,
    tool_context=get_context("tools.bcl_convert"),
) -> List[File]:
    os.makedirs(out_dir, exist_ok=True)

    bclconvert = create_real_or_fake_bcl_convert(
        in_dir=in_dir,
        sample_sheet_path=sample_sheet_path,
        out_dir=out_dir,
        tool_context=tool_context,
    )

    # we only run the real bclconvert via the executor
    if isinstance(bclconvert, FakeBclConvert):
        bclconvert.run()
        return [
            File(os.path.join(out_dir, fastq_file)) for fastq_file in expected_fastq
        ]
    else:
        fastq_files = run_job_n(
            EXECUTOR_CONFIG_PATH_ENV, bclconvert.job_spec
        ).globbed_files[BCLCONVERT_JOB_FASTQ]

        return check_bclconvert(fastq_files, expected_fastq)


@task()
def check_bclconvert(fastq_files: List[File], expected: Set[str]) -> List[File]:
    """Check what we got is what we expected."""
    actual = {fastq_file.basename() for fastq_file in fastq_files}
    if actual != expected:
        anomalies = []
        missing = expected - actual
        unexpected = actual - expected
        if any(missing):
            anomalies.append(
                "failed to find expected fastq files: %s" % ", ".join(sorted(missing))
            )
        if any(unexpected):
            anomalies.append(
                "found unexpected fastq files: %s" % ", ".join(sorted(unexpected))
            )

        raise BclConvertError("; ".join(anomalies))
    return fastq_files


@task()
def fastqc_one(fastq_file: File, out_dir: str) -> File:
    """Run fastqc on a single file, returning just the zip file."""
    os.makedirs(out_dir, exist_ok=True)
    return run_job_1(
        EXECUTOR_CONFIG_PATH_ENV,
        fastqc_job_spec(in_path=fastq_file.path, out_dir=out_dir),
    )


@task()
def fastqc_all(fastq_files: List[File], out_dir: str) -> List[File]:
    """Run fastqc on multiple files, returning just the zip files."""
    return one_forall(fastqc_one, fastq_files, out_dir=out_dir)


@task()
def kmer_sample_one_minsize_if_required(
    fastq_file: File, kmer_sample: FastqSample, rate_sample: File
) -> File:
    if kmer_sample.is_minsize_job_required(
        in_path=fastq_file.path, rate_sample_path=rate_sample.path
    ):
        # overwrite the too-small rate sample with a minsize sample
        return run_job_1(
            EXECUTOR_CONFIG_PATH_ENV,
            kmer_sample.minsize_job_spec(
                in_path=fastq_file.path, out_path=rate_sample.path
            ),
        )
    else:
        return rate_sample


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

    rate_sample = run_job_1(
        EXECUTOR_CONFIG_PATH_ENV,
        kmer_sample.rate_job_spec(in_path=fastq_file.path, out_path=out_path),
    )
    return kmer_sample_one_minsize_if_required(
        fastq_file=fastq_file, kmer_sample=kmer_sample, rate_sample=rate_sample
    )


@task()
def kmer_sample_all(fastq_files: List[File], out_dir: str) -> List[File]:
    """Sample all fastq files as required for kmer analysis."""
    return one_forall(kmer_sample_one, fastq_files, out_dir=out_dir)


@task()
def kmer_analysis_one(fastq_file: File, out_dir: str) -> File:
    """Run kmer analysis for a single fastq file."""
    kmer_prism_workdir = os.path.join(out_dir, "work")
    os.makedirs(kmer_prism_workdir, exist_ok=True)
    kmer_size = 6
    out_path = os.path.join(
        out_dir,
        "%s.k%d.1" % (os.path.basename(fastq_file.path), kmer_size),
    )
    remove_if_exists(out_path)

    return run_job_1(
        EXECUTOR_CONFIG_PATH_ENV,
        kmer_analysis_job_spec(
            in_path=fastq_file.path,
            out_path=out_path,
            input_filetype="fasta",
            kmer_size=kmer_size,
            # kmer_prism drops turds in the current directory and doesn't pickup after itself,
            # so we run with cwd as a subdirectory of the output file
            cwd=kmer_prism_workdir,
        ),
    )


@task()
def kmer_analysis_all(fastq_files: List[File], out_dir: str) -> List[File]:
    """Run kmer analysis for multiple fastq files."""
    return one_forall(kmer_analysis_one, fastq_files, out_dir=out_dir)


@task()
def dedupe_one(
    fastq_file: File,
    out_dir: str,
) -> File:
    """Dedupe a single fastq file."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(fastq_file.path))

    tool_config, _ = get_tool_config(EXECUTOR_CONFIG_PATH_ENV, DEDUPE_TOOL_NAME)
    java_max_heap = tool_config.get("java_max_heap")

    result = run_job_1(
        EXECUTOR_CONFIG_PATH_ENV,
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
    paths: GbsPaths
    spec: GbsTargetSpec
    spec_file: File


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
    return GbsTargetsOutput(
        paths=paths, spec=gbs_target_spec, spec_file=File(paths.target_spec_path)
    )


@dataclass
class Stage1Output:
    fastqc: List[File]
    kmer_analysis: List[File]
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
    sequencer_run = SequencerRun(seq_root, run)

    seq = cook_sample_sheet(
        sequencer_run=sequencer_run, postprocessing_root=postprocessing_root
    )

    fastq_files = bclconvert(
        sequencer_run.dir,
        sample_sheet_path=seq.sample_sheet.path,
        expected_fastq=seq.expected_fastq,
        out_dir=seq.paths.bclconvert_dir,
    )

    fastqc_files = fastqc_all(fastq_files, out_dir=seq.paths.fastqc_dir)

    kmer_samples = kmer_sample_all(fastq_files, out_dir=seq.paths.kmer_fastq_sample_dir)

    kmer_analysis = kmer_analysis_all(kmer_samples, out_dir=seq.paths.kmer_analysis_dir)

    deduped_fastq = dedupe_all(fastq_files, out_dir=seq.paths.dedupe_dir)

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
        kmer_analysis=kmer_analysis,
        spec=gbs_targets.spec,
        spec_file=gbs_targets.spec_file,
        gbs_paths=gbs_targets.paths,
    )
    # kmer_analysis + is troublesome for now because of in-process problems, but should be fixed and returned
