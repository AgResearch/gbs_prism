import glob
import _jsonnet
import json
import os
import os.path
import re
from datetime import timedelta
from redun import File
from redun.task import task, scheduler_task
from redun.scheduler import Job as SchedulerJob, Scheduler
from redun.expression import SchedulerExpression
from redun.promise import Promise
from typing import List, Any, TYPE_CHECKING
from psij import Job, JobAttributes, JobExecutor, JobSpec, JobState, JobStatus


from typing import List, Optional

from agr.util import singleton
import agr.util.cluster as cluster

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


def _create_job_spec(
    config_path_env: str,
    tool: str,
    args: List[str],
    stdout_path: str,
    stderr_path: str,
    cwd: Optional[str] = None,
) -> tuple[JobSpec, str]:
    config = ClusterExecutorConfig(config_path_env)
    tool_config = config.get("tools.default", {}) | config.get(f"tools.{tool}", {})
    executor = tool_config["executor"]
    logger.info(f"tool_config: {tool_config}")

    job_attributes = tool_config.get("job_attributes", {})

    job_prefix = tool_config.get("job_prefix", "")
    job_name = f"{job_prefix}{tool}"

    augmented_custom_attributes = job_attributes.get("custom_attributes", {}) | {
        f"{executor}.job-name": job_name
    }

    job_attributes = (
        job_attributes
        | {"duration": timedelta(**(job_attributes["duration"]))}
        | {"custom_attributes": augmented_custom_attributes}
    )
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
        executor,
    )


def _raise_exception_on_failure(
    job: Job, status: JobStatus | None, spec: cluster.CommonJobSpec
):
    if status is None:
        logger.debug(f"job {job.native_id} status is None")
        raise ClusterExecutorError(f"job {job.native_id} status is None")
    elif status.state == JobState.CANCELED:
        logger.debug(f"job {job.native_id} canceled")
        raise ClusterExecutorError(f"job {job.native_id} canceled")
    elif status.state == JobState.FAILED:
        with open(spec.stderr_path, "r") as stderr_f:
            if status.exit_code is None:
                exit_text = ""
            elif status.exit_code > 128:
                signal = status.exit_code - 128
                exit_text = f" because {'killed' if signal == 9 else ' received signal %d' % signal}"
            else:
                exit_text = f" with exit code {status.exit_code}"
            failure_text = (
                f"failed ({status.message})" if status.message is not None else "failed"
            ) + exit_text
            metadata_text = (
                " ".join(["%s=%s" % (k, str(v)) for k, v in status.metadata])
                if status.metadata is not None
                else ""
            )
            cwd = spec.cwd or os.getcwd()
            command_text = " ".join(spec.args)
            stderr_text = stderr_f.read()
            logger.debug(
                f"job {job.native_id} {command_text} {failure_text} cwd={cwd} {metadata_text}: {stderr_text}"
            )
            raise ClusterExecutorError(
                f"job {job.native_id} {failure_text}\nmetadata: {metadata_text}\ncwd: {cwd}\ncmd: {command_text}\n{stderr_text}"
            )


def _reject_on_failure(
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


@task()
def run_job_1(
    config_path_env: str,
    spec: cluster.Job1Spec,
) -> File:
    """
    Run a job on the defined cluster, which is expected to produce the single file `result_path`

    This function was written before understanding that scheduler tasks are not cached.
    Even so, it is here for now until we work out how to use Promises in tasks, to avoid the
    thread-spawning job.wait() in PSI/J.
    """
    job_spec, executor = _create_job_spec(
        config_path_env=config_path_env,
        tool=spec.tool,
        args=spec.args,
        stdout_path=spec.stdout_path,
        stderr_path=spec.stderr_path,
        cwd=spec.cwd,
    )

    job = Job(job_spec)
    JobExecutor.get_instance(executor).submit(job)

    status = job.wait()
    _raise_exception_on_failure(job, status, spec)

    return File(spec.result_path)


@scheduler_task()
def _run_job_1_uncached(
    scheduler: Scheduler,
    parent_job: SchedulerJob,
    scheduler_expr: SchedulerExpression,
    config_path_env: str,
    spec: cluster.Job1Spec,
) -> Promise[File]:
    """
    Run a job on the defined cluster, which is expected to produce the single file `result_path`

    This function was written before understanding that scheduler tasks are not cached.
    Even so, it is here for now until we work out how to use Promises in tasks, to avoid the
    thread-spawning job.wait() in PSI/J.
    """
    if TYPE_CHECKING:
        # suppress unused parameters
        _ = [x.__class__ for x in [scheduler, parent_job, scheduler_expr]]

    job_spec, executor = _create_job_spec(
        config_path_env=config_path_env,
        tool=spec.tool,
        args=spec.args,
        stdout_path=spec.stdout_path,
        stderr_path=spec.stderr_path,
        cwd=spec.cwd,
    )

    job = Job(job_spec)
    JobExecutor.get_instance(executor).submit(job)

    promise = Promise()

    def job_status_callback(job: Job, status: JobStatus):
        if not _reject_on_failure(promise, job, status, spec.stderr_path):
            logger.debug(f"job {job.native_id} completed")
            if os.path.exists(spec.result_path):
                promise.do_resolve(File(spec.result_path))
            else:
                _ = promise.do_reject(
                    ClusterExecutorError(
                        f"job {job.native_id} failed to write file {spec.result_path}"
                    )
                )

    job.set_job_status_callback(job_status_callback)
    return promise


@task()
def run_job_n(
    config_path_env: str,
    spec: cluster.JobNSpec,
) -> List[File]:
    """
    Run a job on the defined cluster, which is expected to produce files matching `result_glob`
    """

    job_spec, executor = _create_job_spec(
        config_path_env=config_path_env,
        tool=spec.tool,
        args=spec.args,
        stdout_path=spec.stdout_path,
        stderr_path=spec.stderr_path,
        cwd=spec.cwd,
    )

    job = Job(job_spec)
    JobExecutor.get_instance(executor).submit(job)

    status = job.wait()
    _raise_exception_on_failure(job, status, spec)

    files = [
        File(path)
        for path in glob.glob(spec.result_glob)
        if spec.result_reject_re is None
        or re.search(spec.result_reject_re, path) is None
    ]
    return files


def _run_job_n_uncached(
    scheduler: Scheduler,
    parent_job: SchedulerJob,
    scheduler_expr: SchedulerExpression,
    config_path_env: str,
    spec: cluster.JobNSpec,
) -> Promise[List[File]]:
    """
    Run a job on the defined cluster, which is expected to produce files matching `result_glob`

    This function was written before understanding that scheduler tasks are not cached.
    Even so, it is here for now until we work out how to use Promises in tasks, to avoid the
    thread-spawning job.wait() in PSI/J.
    """
    if TYPE_CHECKING:
        # suppress unused parameters
        _ = [x.__class__ for x in [scheduler, parent_job, scheduler_expr]]

    job_spec, executor = _create_job_spec(
        config_path_env=config_path_env,
        tool=spec.tool,
        args=spec.args,
        stdout_path=spec.stdout_path,
        stderr_path=spec.stderr_path,
        cwd=spec.cwd,
    )

    job = Job(job_spec)
    JobExecutor.get_instance(executor).submit(job)

    promise = Promise()

    def job_status_callback(job: Job, status: JobStatus):
        if not _reject_on_failure(promise, job, status, spec.stderr_path):
            logger.debug(f"job {job.native_id} completed")
            files = [
                File(path)
                for path in glob.glob(spec.result_glob)
                if spec.result_reject_re is None
                or re.search(spec.result_reject_re, path) is None
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
