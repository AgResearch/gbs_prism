import os.path
from redun import task, File
from typing import List

from agr.util.subprocess import run_catching_stderr

from .stage2 import Stage2Output

redun_namespace = "agr.gbs_prism"


@task()
def create_peacock(
    run: str,
    postprocessing_root: str,
    gbs_run_root: str,
    stage2: Stage2Output,
) -> List[File]:
    _ = stage2  # depending on existence rather than value
    out_dir = os.path.join(gbs_run_root, "html")
    os.makedirs(out_dir, exist_ok=True)
    peacock_html_path = os.path.join(out_dir, "peacock.html")
    _ = run_catching_stderr(
        [
            "make_cohort_pages",
            "-r",
            run,
            "--postprocessing_root",
            postprocessing_root,
            "-o",
            peacock_html_path,
        ],
        check=True,
    )
    return [File(peacock_html_path)]
