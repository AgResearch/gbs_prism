# helpers for redun
from redun import task, Task
from typing import List, Any

redun_namespace = "agr.util"


@task()
def concat(l1: List[Any], l2: List[Any]) -> List[Any]:
    return l1 + l2


@task()
def one_forall(task: Task, items: List[Any], **kw_task_args) -> List[Any]:
    """Run a task which returns a single item on a list of items."""
    return [task(item, **kw_task_args) for item in items]


@task()
def all_forall(task: Task, items: List[Any], **kw_task_args) -> List[Any]:
    """Run a task which returns a list of items on a list of items."""
    results = []
    for item in items:
        results = concat(results, task(item, **kw_task_args))
    return results
