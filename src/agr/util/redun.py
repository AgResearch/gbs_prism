# helpers for redun
from redun import task, File, Task
from typing import List

redun_namespace = "agr.util"


@task()
def one_forall(task: Task, files: List[File], **kw_task_args) -> List[File]:
    """Run a task which returns a single file on a list of files."""
    return [task(file, kw_task_args) for file in files]


@task()
def _concat_file_lists(files1: List[File], files2: List[File]) -> List[File]:
    return files1 + files2


@task()
def all_forall(task: Task, files: List[File], **kw_task_args) -> List[File]:
    """Run a task which returns a list of files on a list of files."""
    results = []
    for file in files:
        results = _concat_file_lists(results, task(file, kw_task_args))
    return results
