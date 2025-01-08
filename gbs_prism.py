import os.path
from dataclasses import dataclass
from redun import task, File
from typing import List, Literal

redun_namespace = "agr.gbs_prism"

from agr.util.path import gunzipped, gzipped
from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet

# TODO: use real bclconvert not fake one (fake one is very fast)
# from agr.seq.bclconvert import BclConvert
from agr.fake.bclconvert import BclConvert
from agr.seq.dedupe import dedupe
from agr.seq.fastqc import fastqc
from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.config import Config
from agr.gbs_prism.stage1 import Stage1Targets
from agr.gbs_prism.gbs_target_spec import gquery_gbs_target_spec, write_gbs_target_spec
from agr.gbs_prism.kmer_analysis import run_kmer_analysis
from agr.gbs_prism.kmer_prism import KmerPrism
from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import Paths


@dataclass
class CookSampleSheetOutput:
    sample_sheet: File
    dir: str


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
    illumina_platform_root = os.path.join(postprocessing_root, "illumina", platform)
    illumina_platform_run_root = os.path.join(
        illumina_platform_root, sequencer_run.name
    )
    out_path = os.path.join(illumina_platform_run_root, "SampleSheet.csv")
    sample_sheet_dir = os.path.join(illumina_platform_run_root, "SampleSheet")
    os.makedirs(sample_sheet_dir, exist_ok=True)
    sample_sheet.write(out_path)
    return CookSampleSheetOutput(sample_sheet=File(out_path), dir=sample_sheet_dir)


@task()
def main(run: str) -> List[File]:
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
    # bclconvert = BclConvert(
    #     in_dir=sequencer_run.dir,
    #     sample_sheet_path=paths.seq.sample_sheet_path,
    #     out_dir=paths.seq.bclconvert_dir,
    # )
    # kmer_sample = FastqSample(sample_rate=0.0002, minimum_sample_size=10000)
    # kmer_prism = KmerPrism(
    #     input_filetype="fasta",
    #     kmer_size=6,
    #     # this causes it to crash: 😩
    #     # assemble_low_entropy_kmers=True
    # )
    # gbs_keyfiles = GbsKeyfiles(
    #     sequencer_run=sequencer_run,
    #     sample_sheet=sample_sheet,
    #     root=paths.illumina_platform_root,
    #     out_dir=c.keyfiles_dir,
    #     fastq_link_farm=c.fastq_link_farm,
    #     backup_dir=c.gbs_backup_dir,
    # )

    # Ensure we have the directory structure we need in advance
    # paths.make_run_dirs()

    cooked = cook_sample_sheet(
        sequencer_run=sequencer_run, postprocessing_root=c.postprocessing_root
    )

    return [cooked.sample_sheet]
