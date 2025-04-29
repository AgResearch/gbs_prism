import logging
import os
from redun import task, File
from redun.context import get_context
from redun.scheduler import catch_all

from agr.util.path import expand
from agr.redun.cluster_executor import create_cluster_executor_config
from agr.gbs_prism.redun import (
    run_stage1,
    run_stage2,
    run_stage3,
    Stage1Output,
    Stage2Output,
    Stage3Output,
    create_reports,
    warehouse,
)

redun_namespace = "agr.gbs_prism"

logging.basicConfig(
    filename="gbs_prism.log",
    level=logging.DEBUG,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M",
)
# for noisy_module in ["asyncio", "pulp.apis.core", "urllib3"]:
#     logging.getLogger(noisy_module).setLevel(logging.WARN)


MainResults = tuple[Stage1Output, Stage2Output, Stage3Output, list[File], str]


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

    stage3 = run_stage3(stage2=stage2, out_dir=stage1.gbs_paths.report_dir)

    reports = create_reports(
        run=run,
        postprocessing_root=path["postprocessing_root"],
        stage2=stage2,
        out_dir=stage1.gbs_paths.report_dir,
    )

    warehoused = warehouse(
        geno_import_dir=path["geno_import_dir"], log_dir=stage1.gbs_paths.run_root
    )

    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return catch_all((stage1, stage2, stage3, reports, warehoused), Exception, recover)


def init():
    """Early initialization."""
    # initialise cluster executor configuration before anyone needs to use it
    executor_config_env = "GBS_PRISM_EXECUTOR_CONFIG"
    assert (
        executor_config_env in os.environ
    ), f"Missing environment variable {executor_config_env}"
    config_path = os.environ[executor_config_env]
    _ = create_cluster_executor_config(config_path)


init()
