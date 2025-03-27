import os.path
from redun import task, File

from agr.gbs_prism.make_cohort_pages import make_cohort_pages

from .stage2 import Stage2Output

redun_namespace = "agr.gbs_prism"


@task()
def create_peacock(
    run: str,
    postprocessing_root: str,
    gbs_run_root: str,
    stage2: Stage2Output,
) -> list[File]:
    _ = stage2  # depending on existence rather than value
    out_dir = os.path.join(gbs_run_root, "html")
    os.makedirs(out_dir, exist_ok=True)
    peacock_html_path = os.path.join(out_dir, "peacock.html")

    make_cohort_pages(
        postprocessing_root=postprocessing_root, run=run, out_path=peacock_html_path
    )

    return [File(peacock_html_path)]
