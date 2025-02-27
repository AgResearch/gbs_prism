import glob
import _jsonnet
import json
import os
import os.path
import re
from redun import File
from redun.task import scheduler_task
from redun.scheduler import Job as SchedulerJob, Scheduler
from redun.expression import SchedulerExpression
from redun.promise import Promise
from typing import List, Any, TYPE_CHECKING
from psij import Job, JobAttributes, JobExecutor, JobSpec, JobState, JobStatus


from typing import List, Optional

from agr.util import singleton

# TODO remove
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

redun_namespace = "agr.redun"


class ClusterExecutorError(Exception):
    def __init__(
        self,
        message: str,
    ):
        super().__init__(message)


def create_job_spec(
    config_path_env: str,
    tool: str,
    args: List[str],
    stdout_path: str,
    stderr_path: str,
    cwd: Optional[str] = None,
) -> tuple[JobSpec, str]:
    config = ClusterExecutorConfig(config_path_env)
    tool_config = config.get("tools.default", {}) | config.get(f"tools.{tool}", {})
    logger.info(f"tool_config: {tool_config}")

    job_attributes = tool_config.get("job_attributes", {})

    job_prefix = tool_config.get("job_prefix", "")
    job_name = f"{job_prefix}{tool}"

    augmented_custom_attributes = job_attributes.get("custom_attributes", {}) | {
        "job-name": job_name
    }

    job_attributes = job_attributes | {"custom_attributes": augmented_custom_attributes}
    logger.info(f"job_attributes: {job_attributes}")

    return (
        JobSpec(
            executable=args[0],
            arguments=args[1:],
            directory=cwd or os.getcwd(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            attributes=JobAttributes(**job_attributes),
        ),
        tool_config["executor"],
    )


def reject_on_failure(
    promise: Promise, job: Job, status: JobStatus, stderr_path: str
) -> bool:
    if status.state == JobState.CANCELED:
        logger.debug(f"job {job.native_id} canceled")
        _ = promise.do_reject(ClusterExecutorError(f"job {job.native_id} canceled"))
        return True
    elif status.state == JobState.FAILED:
        with open(stderr_path, "r") as stderr_f:
            stderr_text = stderr_f.read()
            logger.debug(f"job {job.native_id} failed: {stderr_text}")
            _ = promise.do_reject(
                ClusterExecutorError(f"job {job.native_id} failed\n{stderr_text}")
            )
        return True
    return False


@scheduler_task()
def run_job_1(
    scheduler: Scheduler,
    parent_job: SchedulerJob,
    scheduler_expr: SchedulerExpression,
    config_path_env: str,
    tool: str,
    args: List[str],
    stdout_path: str,
    stderr_path: str,
    result_path: str,
    cwd: Optional[str] = None,
) -> Promise[File]:
    """
    Run a job on the defined cluster, which is expected to produce the single file `result_path`
    """
    if TYPE_CHECKING:
        # suppress unused parameters
        _ = [x.__class__ for x in [scheduler, parent_job, scheduler_expr]]

    job_spec, executor = create_job_spec(
        config_path_env=config_path_env,
        tool=tool,
        args=args,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        cwd=cwd,
    )

    job = Job(job_spec)
    JobExecutor.get_instance(executor).submit(job)

    promise = Promise()

    def job_status_callback(job: Job, status: JobStatus):
        if not reject_on_failure(promise, job, status, stderr_path):
            logger.debug(f"job {job.native_id} completed")
            if os.path.exists(result_path):
                promise.do_resolve(File(result_path))
            else:
                _ = promise.do_reject(
                    ClusterExecutorError(
                        f"job {job.native_id} failed to write file {result_path}"
                    )
                )

    job.set_job_status_callback(job_status_callback)
    return promise


@scheduler_task()
def run_job_n(
    scheduler: Scheduler,
    parent_job: SchedulerJob,
    scheduler_expr: SchedulerExpression,
    config_path_env: str,
    tool: str,
    args: List[str],
    stdout_path: str,
    stderr_path: str,
    result_glob: str,
    result_reject_re: Optional[str] = None,
    cwd: Optional[str] = None,
) -> Promise[List[File]]:
    """
    Run a job on the defined cluster, which is expected to produce files matching `result_glob`
    """
    if TYPE_CHECKING:
        # suppress unused parameters
        _ = [x.__class__ for x in [scheduler, parent_job, scheduler_expr]]

    job_spec, executor = create_job_spec(
        config_path_env=config_path_env,
        tool=tool,
        args=args,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        cwd=cwd,
    )

    job = Job(job_spec)
    JobExecutor.get_instance(executor).submit(job)

    promise = Promise()

    def job_status_callback(job: Job, status: JobStatus):
        if not reject_on_failure(promise, job, status, stderr_path):
            logger.debug(f"job {job.native_id} completed")
            files = [
                File(path)
                for path in glob.glob(result_glob)
                if result_reject_re is None or re.search(result_reject_re, path) is None
            ]
            promise.do_resolve(files)

    job.set_job_status_callback(job_status_callback)
    return promise


def deep_get(values: Any, path: str, default: Any = None) -> Any:
    for selector in path.split("."):
        values = values.get(selector)
        if values is None:
            return default
    return values


@singleton
class ClusterExecutorConfig:
    def __init__(self, config_path_env):
        assert (
            config_path_env in os.environ
        ), f"Missing environment variable {config_path_env}"
        config_path = os.environ[config_path_env]
        with open(config_path, "r") as config_f:
            raw_config = config_f.read()
            json_config = _jsonnet.evaluate_snippet(config_path, raw_config)
            self._config = json.loads(json_config)

    def get(self, path: str, default: Any = None) -> Any:
        return deep_get(self._config, path, default=default)
