import dominate
from dominate.tags import h1


def make_kgd_cohort_report(target_cohort_dir: str, cohort_name: str, out_path: str):
    title = "Results for KGD for %s" % cohort_name
    doc = dominate.document(title=title)
    doc += h1(title)

    with open(out_path, "w") as out_f:
        _ = out_f.write(str(doc))
