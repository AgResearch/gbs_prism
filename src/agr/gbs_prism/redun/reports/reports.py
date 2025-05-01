import os.path
from redun import task, File

from ..stage1 import Stage1Output
from ..stage2 import Stage2Output
from ..stage3 import Stage3Output

from .peacock import create_peacock_report

redun_namespace = "agr.gbs_prism.reports"


@task()
def create_reports(
    run: str,
    stage1: Stage1Output,
    stage2: Stage2Output,
    stage3: Stage3Output,
    out_dir: str,
) -> list[File]:
    _ = stage2  # depending on existence rather than value
    os.makedirs(out_dir, exist_ok=True)
    all_reports = []

    peacock_html_path = os.path.join(out_dir, "peacock.html")
    all_reports.append(
        create_peacock_report(
            title=run,
            stage1=stage1,
            stage2=stage2,
            stage3=stage3,
            out_path=peacock_html_path,
        )
    )
    return all_reports
