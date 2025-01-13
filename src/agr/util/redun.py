# helpers for redun
from redun import task, File, Task
from typing import List, Any

redun_namespace = "agr.util"


@task()
def one_forall(task: Task, args: List[Any], **kw_task_args) -> List[Any]:
    """Run a task which returns a single result once for each arg."""
    return [task(arg, kw_task_args) for arg in args]


@task()
def lazy_concat(l1: List[Any], l2: List[Any]) -> List[Any]:
    return l1 + l2


@task()
def all_forall(task: Task, args: List[Any], **kw_task_args) -> List[Any]:
    """Run a task which returns a list of results once for each arg."""
    all_results = []
    for arg in args:
        all_results = lazy_concat(all_results, task(arg, kw_task_args))
    return all_results


@task()
def file_from_path(path: str) -> File:
    """
    Alas the typing here does not work, because of the @task decorators.

    `path` is passed in as bytes, since that's what gets output on stdout of a script,
    but scripts look like they return `str`.

    Being honest with the type of `path` input parameter here would mean we would have to suppress
    type errors wherever this is called.
    """
    assert isinstance(path, bytes), path
    path_s = path.decode("utf-8")
    assert isinstance(path_s, str), path_s
    return File(path_s)
