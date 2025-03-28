import os.path
from redun import task, File

from agr.gbs_prism.paths import GbsPaths
from agr.gbs_prism.make_cohort_pages import make_cohort_pages
from agr.gbs_prism.reports import make_kgd_cohort_report
from .stage2 import Stage2Output

redun_namespace = "agr.gbs_prism"


@task()
def create_peacock(run: str, postprocessing_root: str, out_path) -> File:
    make_cohort_pages(
        postprocessing_root=postprocessing_root, run=run, out_path=out_path
    )

    return File(out_path)


@task()
def create_kgd_cohort_report(
    target_cohort_dir: str, cohort_name: str, out_path: str
) -> File:
    # TODO should take redun file output from KGD
    make_kgd_cohort_report(
        target_cohort_dir=target_cohort_dir, cohort_name=cohort_name, out_path=out_path
    )
    return File(out_path)


@task()
def create_reports(
    run: str,
    postprocessing_root: str,
    gbs_paths: GbsPaths,
    stage2: Stage2Output,
) -> list[File]:
    _ = stage2  # depending on existence rather than value
    out_dir = os.path.join(gbs_paths.run_root, "html")
    os.makedirs(out_dir, exist_ok=True)
    all_reports = []

    peacock_html_path = os.path.join(out_dir, "peacock.html")
    all_reports.append(
        create_peacock(
            postprocessing_root=postprocessing_root, run=run, out_path=peacock_html_path
        )
    )

    # TODO actually use cohort output here, for files we are accessing
    for cohort_name in stage2.cohorts:
        cohort_report_dir = os.path.join(out_dir, cohort_name)
        os.makedirs(cohort_report_dir, exist_ok=True)
        all_reports.append(
            create_kgd_cohort_report(
                # TODO use unblinded results, not blinded?
                target_cohort_dir=gbs_paths.cohort_blind_dir(cohort_name),
                cohort_name=cohort_name,
                out_path=os.path.join(cohort_report_dir, "KGD.html"),
            )
        )

    return all_reports
