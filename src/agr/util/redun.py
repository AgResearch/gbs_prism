# helpers for redun
from redun import task, File, Task
from typing import List

redun_namespace = "agr.util"


@task()
def one_forall(task: Task, task_args, files: List[File]) -> List[File]:
    """Run a task which returns a single file on a list of files."""
    return [task(file, task_args) for file in files]


@task()
def _concat_file_lists(files1: List[File], files2: List[File]) -> List[File]:
    return files1 + files2


@task()
def all_forall(task: Task, task_args, files: List[File]) -> List[File]:
    """Run a task which returns a list of files on a list of files."""
    results = []
    for file in files:
        results = _concat_file_lists(results, task(file, task_args))
    return results
