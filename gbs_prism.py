import os.path
from dataclasses import dataclass
from redun import task, File
from typing import Dict, List, Literal, Set

redun_namespace = "agr.gbs_prism"

from agr.util.legacy import sanitised_realpath
from agr.util.path import remove_if_exists
from agr.util.redun import one_forall, all_forall
from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet

# TODO: use real bclconvert not fake one (fake one is very fast)
# from agr.seq.bclconvert import BclConvert
from agr.fake.bclconvert import BclConvert
from agr.seq.dedupe import dedupe
from agr.seq.fastqc import fastqc
from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.config import Config
from agr.gbs_prism.gbs_target_spec import (
    gquery_gbs_target_spec,
    write_gbs_target_spec,
    GbsTargetSpec,
)
from agr.gbs_prism.kmer_analysis import run_kmer_analysis
from agr.gbs_prism.kmer_prism import KmerPrism
from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import SeqPaths, GbsPaths


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
    in_dir: str, sample_sheet_path: str, expected_fastq: Set[str], out_dir: str
) -> List[File]:
    os.makedirs(out_dir, exist_ok=True)
    bclconvert = BclConvert(
        in_dir=in_dir,
        sample_sheet_path=sample_sheet_path,
        out_dir=out_dir,
    )
    bclconvert.run()
    bclconvert.check_expected_fastq_files(expected_fastq)
    return [File(os.path.join(out_dir, fastq_file)) for fastq_file in expected_fastq]


@task()
def fastqc_one(fastq_file: File, kwargs) -> List[File]:
    """Run fastqc on a single file, returning both the html and zip results."""
    out_dir = kwargs["out_dir"]
    fastqc(in_path=fastq_file.path, out_dir=out_dir)
    basename = (
        os.path.basename(fastq_file.path).removesuffix(".gz").removesuffix(".fastq")
    )
    return [
        File(os.path.join(out_dir, "%s%s" % (basename, ext)))
        for ext in ["_fastqc.html", "_fastqc.zip"]
    ]


@task()
def fastqc_all(fastq_files: List[File], out_dir: str) -> List[File]:
    """Run fastqc on multiple files, returning concatenation of all the html and zip results."""
    return all_forall(fastqc_one, fastq_files, out_dir=out_dir)


@task()
def kmer_sample_one(fastq_file: File, kwargs) -> File:
    """Sample a single fastq file as required for kmer analysis."""
    out_dir = kwargs["out_dir"]
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
def kmer_analysis_one(fastq_file: File, kwargs) -> File:
    """Run kmer analysis for a single fastq file."""
    out_dir = kwargs["out_dir"]
    kmer_prism = kwargs["kmer_prism"]
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir,
        "%s.%s.1" % (os.path.basename(fastq_file.path), kmer_prism.moniker),
    )
    run_kmer_analysis(in_path=fastq_file.path, out_path=out_path, kmer_prism=kmer_prism)
    return File(out_path)


@task()
def kmer_analysis_all(
    fastq_files: List[File], out_dir: str, kmer_prism: KmerPrism
) -> List[File]:
    """Run kmer analysis for multiple fastq files."""
    return one_forall(
        kmer_analysis_one, fastq_files, out_dir=out_dir, kmer_prism=kmer_prism
    )


@task()
def dedupe_one(fastq_file: File, kwargs) -> File:
    """Dedupe a single fastq file."""
    out_dir = kwargs["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(fastq_file.path))
    dedupe(
        in_path=fastq_file.path,
        out_path=out_path,
        tmp_dir="/tmp",  # TODO maybe need tmp_dir on large scratch partition
        jvm_args=[],
    )  # TODO fallback to default of 80g which Dedupe uses if we don't override it here
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
    _deduped_fastq_files: List[File],
    root: str,
    out_dir: str,
    fastq_link_farm: str,
    backup_dir: str,
) -> List[File]:
    """Get GBS keyfiles, which must depend on deduped fastq files having been produced."""
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
    spec_file: File
    spec: GbsTargetSpec


@task()
def get_gbs_targets(
    run: str, postprocessing_root: str, fastq_link_farm: str, _gbs_keyfiles: List[File]
) -> GbsTargetsOutput:
    """Get GBS target spec, which must depend on GBS keyfiles having been produced."""
    gbs_root = os.path.join(postprocessing_root, "gbs")
    paths = GbsPaths(root=gbs_root, run=run)
    os.makedirs(paths.run_root, exist_ok=True)
    gbs_target_spec = gquery_gbs_target_spec(run, fastq_link_farm)
    write_gbs_target_spec(paths.target_spec_path, gbs_target_spec)
    return GbsTargetsOutput(
        paths=paths, spec_file=File(paths.target_spec_path), spec=gbs_target_spec
    )


@task
def create_cohort_fastq_links(gbs_targets: GbsTargetsOutput) -> Dict[str, List[File]]:
    """Link the fastq files for each cohort separately.

    So that subsequent dependencies can be properly captured in wildcarded paths.
    """
    links_by_cohort = {}
    for cohort_name, spec in gbs_targets.spec.cohorts.items():
        cohort_links = []
        for fastq_basename, fastq_link in spec.fastq_links.items():
            # create the same links in both blind and unblind directories
            for blind in [False, True]:
                link_dir = gbs_targets.paths.fastq_link_dir(
                    str(cohort_name), blind=blind
                )
                os.makedirs(link_dir, exist_ok=True)
                link = os.path.join(
                    link_dir,
                    fastq_basename,
                )
                # Python should really support ln -sf, bah!
                remove_if_exists(link)
                os.symlink(sanitised_realpath(fastq_link), link)
                cohort_links.append(File(link))
        links_by_cohort[cohort_name] = cohort_links
    return links_by_cohort


@task()
def main(run: str) -> tuple[List[File], List[Dict[str, List[File]]]]:
    c = Config(
        run=run,
        # pipeline config for gbs_prism
        # TODO:
        # seq_root = "/dataset/2024_illumina_sequencing_e/active",
        # seq_root="/dataset/2024_legacy_playpen/scratch/gbs_prism.dev/fake_runs",
        seq_root="/dataset/2024_legacy_playpen/scratch/gbs_prism.dev/fake_runs",
        # seq_root="~/share/agr/gbs_prism.dev/fake_runs",
        # TODO:
        # postprocessing_root = "/dataset/2024_illumina_sequencing_d/scratch/postprocessing",
        # postprocessing_root = "/dataset/2024_legacy_playpen/scratch/gbs_prism.dev/postprocessing",
        postprocessing_root="/dataset/2024_legacy_playpen/scratch/gbs_prism.redun/postprocessing",
        # postprocessing_root="~/share/agr/gbs_prism.dev/postprocessing",
        # TODO:
        # gbs_backup_dir = "/dataset/gseq_processing/archive/backups",
        # gbs_backup_dir = "/dataset/2024_legacy_playpen/scratch/gbs_prism.dev/backups",
        gbs_backup_dir="/dataset/2024_legacy_playpen/scratch/gbs_prism.redun/backups",
        # gbs_backup_dir="~/share/agr/gbs_prism.dev/backups",
        # TODO:
        # keyfiles_dir = "/dataset/hiseq/active/key-files",
        # keyfiles_dir = "/dataset/2024_legacy_playpen/scratch/gbs_prism.dev/key-files",
        keyfiles_dir="/dataset/2024_legacy_playpen/scratch/gbs_prism.redun/key-files",
        # keyfiles_dir="~/share/agr/gbs_prism.dev/key-files",
        # TODO
        # fastq_link_farm = "/dataset/hiseq/active/fastq-link-farm",
        # fastq_link_farm = "/dataset/2024_legacy_playpen/scratch/gbs_prism.dev/fastq-link-farm"
        fastq_link_farm="/dataset/2024_legacy_playpen/scratch/gbs_prism.redun/fastq-link-farm",
        # fastq_link_farm="~/share/agr/gbs_prism.dev/fastq-link-farm",
    )

    sequencer_run = SequencerRun(c.seq_root, c.run)

    # paths = Paths(c.postprocessing_root, c.run)
    # stage1 = Stage1Targets(c.run, sample_sheet, paths.seq)

    # Ensure we have the directory structure we need in advance
    # paths.make_run_dirs()

    seq = cook_sample_sheet(
        sequencer_run=sequencer_run, postprocessing_root=c.postprocessing_root
    )

    fastq_files = bclconvert(
        sequencer_run.dir,
        sample_sheet_path=seq.sample_sheet.path,
        expected_fastq=seq.expected_fastq,
        out_dir=seq.paths.bclconvert_dir,
    )

    fastqc_files = fastqc_all(fastq_files, out_dir=seq.paths.fastqc_dir)

    kmer_samples = kmer_sample_all(fastq_files, out_dir=seq.paths.kmer_fastq_sample_dir)

    kmer_prism = KmerPrism(
        input_filetype="fasta",
        kmer_size=6,
        # this causes it to crash: 😩
        # assemble_low_entropy_kmers=True
    )
    kmer_analysis = kmer_analysis_all(
        kmer_samples, out_dir=seq.paths.kmer_analysis_dir, kmer_prism=kmer_prism
    )

    deduped_fastq = dedupe_all(fastq_files, out_dir=seq.paths.dedupe_dir)

    gbs_keyfiles = get_gbs_keyfiles(
        sequencer_run=sequencer_run,
        sample_sheet=seq.sample_sheet,
        gbs_libraries=seq.gbs_libraries,
        _deduped_fastq_files=deduped_fastq,
        root=seq.illumina_platform_root,
        out_dir=c.keyfiles_dir,
        fastq_link_farm=c.fastq_link_farm,
        backup_dir=c.gbs_backup_dir,
    )

    gbs_targets = get_gbs_targets(
        run=run,
        postprocessing_root=c.postprocessing_root,
        fastq_link_farm=c.fastq_link_farm,
        _gbs_keyfiles=gbs_keyfiles,
    )

    cohort_fastq_links = create_cohort_fastq_links(gbs_targets)

    return (
        fastqc_files + deduped_fastq + gbs_keyfiles + [gbs_targets.spec_file],
        [cohort_fastq_links],
    )
    # kmer_analysis + is troublesome for now because of in-process problems
