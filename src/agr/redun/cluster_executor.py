import glob
import _jsonnet
import json
import os
import os.path
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from redun import File
from redun.task import task, scheduler_task
from redun.scheduler import Job as SchedulerJob, Scheduler
from redun.expression import SchedulerExpression
from redun.promise import Promise
from psij import (
    Job,
    JobAttributes,
    JobExecutor,
    JobSpec,
    JobState,
    JobStatus,
)
from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutorConfig
from typing import Any, Optional, TYPE_CHECKING

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


class ConfigError(Exception):
    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        tool: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        self.message = message
        self.path = path
        self.tool = tool
        # cause is explicit so we can format it into the base Exception class
        # which is required for redun to show it in the console,
        # and this is the reason we don't use raise from and ex.__cause__
        self.cause = cause
        super().__init__(str(self))

    def __str__(self) -> str:
        result = "Configuration error"
        if self.tool is not None:
            result += f" for {self.tool}"
        if self.path is not None:
            result += f" in {self.path}"
        result += f": {self.message}"
        if self.cause is not None:
            result += f": {type(self.cause).__name__} {str(self.cause)}"
        return result


@dataclass(kw_only=True)
class CommonJobSpec:
    """The spec in common for any job to run on the compute cluster."""

    tool: str
    args: list[str]
    stdout_path: str
    stderr_path: str
    cwd: Optional[str] = None


@dataclass(kw_only=True)
class Job1Spec(CommonJobSpec):
    """For jobs which produce a single file whose path is known in advance."""

    expected_path: str


@dataclass
class FilteredGlob:
    """A file glob optionally without any paths matched by `reject_re`."""

    glob: str
    reject_re: Optional[str] = None


@dataclass(kw_only=True)
class JobNSpec(CommonJobSpec):
    """
    For jobs which produce multiple files with paths matching the glob, exluding any matched by the regex.

    As many conbinations of globs and paths may be expected, in a dict whose keys are arbitrary strings.
    Result files will be returned in a dict with the same keys.
    """

    # each value is either a result path or a filtered glob
    expected_paths: dict[str, str]
    expected_globs: dict[str, FilteredGlob]


def _create_job_attributes(
    configured_attributes: dict[str, Any],
    executor_name: str,
    job_name: str,
) -> JobAttributes:
    augmented_custom_attributes = {
        "custom_attributes": (
            configured_attributes.get("custom_attributes", {})
            | {
                f"{executor_name}.job-name": job_name,
            }
        )
    }

    if configured_duration := configured_attributes.get("duration"):
        try:
            duration = timedelta(**configured_duration)
        except TypeError as err:
            raise ConfigError(
                "invalid duration, must be dict with fields as per timedelta constructor with integer values",
                cause=err,
            )
        duration_attribute = {"duration": duration}
    else:
        duration_attribute = {}

    attributes = (
        configured_attributes | duration_attribute | augmented_custom_attributes
    )
    logger.info(f"job_attributes: {attributes}")

    return JobAttributes(**attributes)


def _create_job_spec(
    spec: CommonJobSpec,
) -> tuple[JobSpec, str]:
    tool_config, config_path = get_tool_config_and_path(spec.tool)
    try:
        executor_name = tool_config["executor"]
        job_prefix = tool_config.get("job_prefix", "")

        job_attributes = _create_job_attributes(
            configured_attributes=tool_config.get("job_attributes", {}),
            executor_name=executor_name,
            job_name=f"{job_prefix}{spec.tool}",
        )

        return (
            JobSpec(
                executable=spec.args[0],
                arguments=spec.args[1:],
                directory=spec.cwd or os.getcwd(),
                stdout_path=spec.stdout_path,
                stderr_path=spec.stderr_path,
                attributes=job_attributes,
            ),
            executor_name,
        )
    except ConfigError as err:
        if err.path is not None and err.tool is not None:
            raise
        else:
            raise ConfigError(
                message=err.message, path=config_path, tool=spec.tool, cause=err.cause
            )
    except Exception as ex:
        raise ConfigError(message=str(ex), path=config_path, cause=ex)


def _create_executor(executor_name: str):
    # PSI/J defaults to home directory, which is not what we want
    cwd = os.getcwd()
    psij_dir = os.path.join(cwd, ".psij")

    return JobExecutor.get_instance(
        executor_name,
        # alas we really do need to instantiate a BatchSchedulerExecutorConfig rather than a JobExecutorConfig,
        # because the latter is an abstract base class which does not set the required defaults like initial_queue_polling_delay
        # https://github.com/ExaWorks/psij-python/issues/511
        config=BatchSchedulerExecutorConfig(
            launcher_log_file=Path(psij_dir),
            work_directory=Path(cwd),
        ),
    )


def job_description(
    job: Job,
    spec: CommonJobSpec,
    annotation: Optional[str] = None,
    multiline: bool = False,
) -> str:
    cwd = spec.cwd or os.getcwd()
    command_text = " ".join(spec.args)
    padded_annotation = f" {annotation}" if annotation is not None else ""
    if multiline:
        return (
            f"job {job.native_id}{padded_annotation}\ncwd: {cwd}\ncmd: {command_text}\n"
        )
    else:
        return f"job {job.native_id} {command_text}{padded_annotation} cwd={cwd}"


def _raise_exception_on_failure(
    job: Job, status: JobStatus | None, spec: CommonJobSpec
):
    if status is None:
        logger.debug(f"job {job.native_id} status is None")
        raise ClusterExecutorError(f"job {job.native_id} status is None")
    elif status.state == JobState.CANCELED:
        logger.debug(f"job {job.native_id} canceled")
        raise ClusterExecutorError(f"job {job.native_id} canceled")
    elif status.state == JobState.FAILED:
        try:
            with open(spec.stderr_path, "r") as stderr_f:
                stderr_text = stderr_f.read()
        except:
            stderr_text = (
                f"(stderr unavailable because failed to read {spec.stderr_path})"
            )
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
        logger.debug(
            f"{job_description(job, spec, annotation=failure_text)} {metadata_text}: {stderr_text}"
        )
        raise ClusterExecutorError(
            f"{job_description(job, spec, annotation=failure_text, multiline=True)}\nmetadata: {metadata_text}\n{stderr_text}"
        )


def _reject_on_failure(
    promise: Promise, job: Job, status: JobStatus, stderr_path: str
) -> bool:
    if status.state == JobState.CANCELED:
        logger.debug(f"job {job.native_id} canceled")
        _ = promise.do_reject(ClusterExecutorError(f"job {job.native_id} canceled"))
        return True
    elif status.state == JobState.FAILED:
        try:
            with open(stderr_path, "r") as stderr_f:
                stderr_text = stderr_f.read()
        except:
            stderr_text = f"(stderr unavailable because failed to read {stderr_path})"
        logger.debug(f"job {job.native_id} failed: {stderr_text}")
        _ = promise.do_reject(
            ClusterExecutorError(f"job {job.native_id} failed\n{stderr_text}")
        )
        return True
    return False


@task()
def run_job_1(
    spec: Job1Spec,
) -> File:
    """
    Run a job on the defined cluster, which is expected to produce the single file `result_path`
    """
    job_spec, executor_name = _create_job_spec(
        spec=spec,
    )

    job = Job(job_spec)
    _create_executor(executor_name).submit(job)

    status = job.wait()
    _raise_exception_on_failure(job, status, spec)

    if not os.path.exists(spec.expected_path):
        raise ClusterExecutorError(
            f"{job_description(job, spec, annotation=f'failed to create {spec.expected_path}', multiline=True)}"
        )

    return File(spec.expected_path)


@scheduler_task()
def _run_job_1_uncached(
    scheduler: Scheduler,
    parent_job: SchedulerJob,
    scheduler_expr: SchedulerExpression,
    spec: Job1Spec,
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

    job_spec, executor_name = _create_job_spec(
        spec=spec,
    )

    job = Job(job_spec)
    _create_executor(executor_name).submit(job)

    promise = Promise()

    def job_status_callback(job: Job, status: JobStatus):
        if not _reject_on_failure(promise, job, status, spec.stderr_path):
            logger.debug(f"job {job.native_id} completed")
            if os.path.exists(spec.expected_path):
                promise.do_resolve(File(spec.expected_path))
            else:
                _ = promise.do_reject(
                    ClusterExecutorError(
                        f"{job_description(job, spec, annotation=f'failed to create {spec.expected_path}', multiline=True)}"
                    )
                )

    job.set_job_status_callback(job_status_callback)
    return promise


# it's here as a basis for future work
_ = _run_job_1_uncached


@dataclass
class ResultFiles:
    expected_files: dict[str, File]
    globbed_files: dict[str, list[File]]


def _result_files(
    job: Job,
    spec: CommonJobSpec,
    expected_paths: dict[str, str],
    expected_globs: dict[str, FilteredGlob],
) -> ResultFiles:
    """Return result files for expected paths, or those matching filtered glob."""
    for k, path in expected_paths.items():
        if not os.path.exists(path):
            raise ClusterExecutorError(
                f"{job_description(job, spec, annotation=f'failed to create {k}={path}', multiline=True)}"
            )

    return ResultFiles(
        expected_files={k: File(path) for (k, path) in expected_paths.items()},
        globbed_files={
            k: [
                File(path)
                for path in glob.glob(expected.glob)
                if expected.reject_re is None
                or re.search(expected.reject_re, path) is None
            ]
            for (k, expected) in expected_globs.items()
        },
    )


@task()
def run_job_n(
    spec: JobNSpec,
) -> ResultFiles:
    """
    Run a job on the defined cluster, which is expected to produce files matching `result_glob`
    """

    job_spec, executor_name = _create_job_spec(
        spec=spec,
    )

    job = Job(job_spec)
    _create_executor(executor_name).submit(job)

    status = job.wait()
    _raise_exception_on_failure(job, status, spec)

    return _result_files(job, spec, spec.expected_paths, spec.expected_globs)


def _run_job_n_uncached(
    scheduler: Scheduler,
    parent_job: SchedulerJob,
    scheduler_expr: SchedulerExpression,
    spec: JobNSpec,
) -> Promise[ResultFiles]:
    """
    Run a job on the defined cluster, which is expected to produce files matching `result_glob`

    This function was written before understanding that scheduler tasks are not cached.
    Even so, it is here for now until we work out how to use Promises in tasks, to avoid the
    thread-spawning job.wait() in PSI/J.
    """
    if TYPE_CHECKING:
        # suppress unused parameters
        _ = [x.__class__ for x in [scheduler, parent_job, scheduler_expr]]

    job_spec, executor_name = _create_job_spec(spec=spec)

    job = Job(job_spec)
    _create_executor(executor_name).submit(job)

    promise = Promise()

    def job_status_callback(job: Job, status: JobStatus):
        if not _reject_on_failure(promise, job, status, spec.stderr_path):
            logger.debug(f"job {job.native_id} completed")
            files = _result_files(job, spec, spec.expected_paths, spec.expected_globs)
            promise.do_resolve(files)

    job.set_job_status_callback(job_status_callback)
    return promise


# it's here as a basis for future work
_ = _run_job_n_uncached


def deep_get(values: Any, path: str, default: Any = None) -> Any:
    for selector in path.split("."):
        values = values.get(selector)
        if values is None:
            return default
    return values


def get_config_path(config_path_env: str) -> str:
    assert (
        config_path_env in os.environ
    ), f"Missing environment variable {config_path_env}"
    return os.environ[config_path_env]


@singleton
class ClusterExecutorConfig:
    def __init__(self):
        self._configured = False
        self._path = None

    @property
    def path(self) -> str:
        assert (
            self._path is not None
        ), "ClusterExecutorConfig is not configured, need an early call to read_config()"

        return self._path

    def read_config(self, path: str):
        try:
            with open(path, "r") as config_f:
                raw_config = config_f.read()
                json_config = _jsonnet.evaluate_snippet(path, raw_config)
                self._config = json.loads(json_config)
        except Exception as ex:
            raise ConfigError(
                message="invalid Jsonnet configuration", path=path, cause=ex
            )
        self._configured = True
        self._path = path

    def get(self, path: str, default: Any = None) -> Any:
        assert (
            self._configured
        ), "ClusterExecutorConfig is not configured, need an early call to read_config()"
        return deep_get(self._config, path, default=default)


def get_tool_config_and_path(tool: str) -> tuple[dict[str, Any], str]:
    """Return tool config and config path, assuming the singleton object has been configured."""
    config = ClusterExecutorConfig()
    tool_config = config.get("tools.default", {}) | config.get(f"tools.{tool}", {})
    logger.info(f"{tool} config: {tool_config}")
    return tool_config, config.path


def get_tool_config(tool: str) -> dict[str, Any]:
    """Return tool config only."""
    return get_tool_config_and_path(tool)[0]


def create_cluster_executor_config(
    config_path: str,
):
    """
    Create the cluster executor configuration.
    Must be done before any configuration may be accessed.
    """
    cluster_config = ClusterExecutorConfig()
    cluster_config.read_config(config_path)
