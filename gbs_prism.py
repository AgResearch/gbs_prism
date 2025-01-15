from redun import task, File
from redun.context import get_context
from typing import List

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

    stage1 = run_stage1(
        seq_root=get_context("path.seq_root"),
        postprocessing_root=get_context("path.postprocessing_root"),
        gbs_backup_dir=get_context("path.gbs_backup_dir"),
        keyfiles_dir=get_context("path.keyfiles_dir"),
        fastq_link_farm=get_context("path.fastq_link_farm"),
        run=run,
    )

    stage2 = run_stage2(run=run, spec=stage1.spec, gbs_paths=stage1.gbs_paths)

    peacock = create_peacock(
        run=run,
        postprocessing_root=get_context("path.postprocessing_root"),
        gbs_run_root=stage1.gbs_paths.run_root,
        stage2=stage2,
    )
    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return (stage1, stage2, peacock)
