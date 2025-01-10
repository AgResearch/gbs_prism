# helpers for redun
from redun import task, Task
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
