# helpers for redun
import os.path
from redun import task, Task, File
from typing import Any, Callable

redun_namespace = "agr.util"


class PathError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


@task()
def concat(l1: list[Any], l2: list[Any]) -> list[Any]:
    return l1 + l2


@task()
def one_forall(task: Task, items: list[Any], **kw_task_args) -> list[Any]:
    """Run a task which returns a single item on a list of items."""
    return [task(item, **kw_task_args) for item in items]


@task()
def one_foreach(task: Task, items: dict[Any, Any], **kw_task_args) -> dict[Any, Any]:
    """Run a task which returns a single item on a dict of items, returning results in a dict with same keys."""
    return {key: task(item, **kw_task_args) for (key, item) in items.items()}


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


def existing_file(path: str) -> File:
    """Return path as file, failing if it doesn't exist."""
    if os.path.exists(path):
        return File(path)
    else:
        raise PathError(f"no such file: {path}")
