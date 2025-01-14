from redun import task, File
from typing import List

from agr.gbs_prism.config import Config
from agr.gbs_prism.redun import (
    run_stage1,
    run_stage2,
    Stage1Output,
    Stage2Output,
    create_peacock,
)

redun_namespace = "agr.gbs_prism"


@task()
def main(
    run: str,
) -> tuple[Stage1Output, Stage2Output, List[File]]:
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

    stage1 = run_stage1(
        seq_root=c.seq_root,
        postprocessing_root=c.postprocessing_root,
        gbs_backup_dir=c.gbs_backup_dir,
        keyfiles_dir=c.keyfiles_dir,
        fastq_link_farm=c.fastq_link_farm,
        run=run,
    )

    stage2 = run_stage2(run=run, spec=stage1.spec, gbs_paths=stage1.gbs_paths)

    peacock = create_peacock(
        run=run,
        postprocessing_root=c.postprocessing_root,
        gbs_run_root=stage1.gbs_paths.run_root,
        stage2=stage2,
    )
    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return (stage1, stage2, peacock)
