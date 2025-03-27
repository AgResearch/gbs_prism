# helpers for redun
from redun import task, Task
from typing import Any, Callable

redun_namespace = "agr.util"


@task()
def concat(l1: list[Any], l2: list[Any]) -> list[Any]:
    return l1 + l2


@task()
def one_forall(task: Task, items: list[Any], **kw_task_args) -> list[Any]:
    """Run a task which returns a single item on a list of items."""
    return [task(item, **kw_task_args) for item in items]


@task()
def all_forall(task: Task, items: list[Any], **kw_task_args) -> list[Any]:
    """Run a task which returns a list of items on a list of items."""
    results = []
    for item in items:
        results = concat(results, task(item, **kw_task_args))
    return results


@task()
def lazy_map(x: Any, f: Callable[[Any], Any]) -> Any:
    """Map f over the expression `x`."""
    return f(x)
