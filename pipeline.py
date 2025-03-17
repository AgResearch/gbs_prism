import logging
from redun import task, File
from redun.context import get_context
from redun.scheduler import catch_all
from typing import List

from agr.util.path import expand
from agr.gbs_prism.redun import (
    run_stage1,
    run_stage2,
    Stage1Output,
    Stage2Output,
    create_peacock,
)

redun_namespace = "agr.gbs_prism"

logging.basicConfig(
    filename="gbs_prism.log",
    level=logging.INFO,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M",
)
# for noisy_module in ["asyncio", "pulp.apis.core", "urllib3"]:
#     logging.getLogger(noisy_module).setLevel(logging.WARN)


MainResults = tuple[Stage1Output, Stage2Output, List[File]]


@task()
def recover(results: MainResults) -> MainResults:
    """
    Recovery is not currently attempted, but having the catch_all is enough to ensure
    we loiter until all tasks are done or failed.
    """
    return results


@task()
def main(
    run: str,
    path_context=get_context("path"),
) -> MainResults:

    path = {k: expand(v) for (k, v) in path_context.items()}

    stage1 = run_stage1(
        seq_root=path["seq_root"],
        postprocessing_root=path["postprocessing_root"],
        gbs_backup_dir=path["gbs_backup_dir"],
        keyfiles_dir=path["keyfiles_dir"],
        fastq_link_farm=path["fastq_link_farm"],
        run=run,
    )

    stage2 = run_stage2(run=run, spec=stage1.spec, gbs_paths=stage1.gbs_paths)

    peacock = create_peacock(
        run=run,
        postprocessing_root=path["postprocessing_root"],
        gbs_run_root=stage1.gbs_paths.run_root,
        stage2=stage2,
    )
    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return catch_all((stage1, stage2, peacock), Exception, recover)
