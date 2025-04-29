import os.path
import re
from redun import task, File

from agr.redun import existing_file
from agr.util.subprocess import run_catching_stderr


@task()
def collate_barcode_yields(uneak_stdout_files: dict[str, File], out_path: str) -> File:
    stats_dict = {}

    #  example = """
    # Total number of reads in lane=243469299
    # Total number of good barcoded reads=199171115
    # """

    for cohort_name, uneak_stdout_file in uneak_stdout_files.items():
        sample_ref = cohort_name

        yield_stats = [0.0, 0.0]  # will contain total reads, total good barcoded

        with open(uneak_stdout_file.path, "r") as f:
            for record in f:
                hit = re.search(
                    r"^Total number of reads in lane=(\d+)$", record.strip()
                )
                if hit is not None:
                    yield_stats[1] += float(hit.groups()[0])
                hit = re.search(
                    r"^Total number of good barcoded reads=(\d+)$", record.strip()
                )
                if hit is not None:
                    yield_stats[0] += float(hit.groups()[0])

        stats_dict[sample_ref] = yield_stats

    with open(out_path, "w") as out_f:
        print("\t".join(("sample_ref", "good_pct", "good_std")), file=out_f)
        for sample_ref in sorted(stats_dict.keys()):
            out_rec = [sample_ref, "0", "0"]

            n = stats_dict[sample_ref][1]
            if n > 0:
                p = stats_dict[sample_ref][0] / stats_dict[sample_ref][1]
            else:
                p = 0

            q = 1 - p
            stddev = 0.0
            if n > 0:
                stddev = (p * q / n) ** 0.5
            out_rec[1] = str(p * 100.0)
            out_rec[2] = str(stddev * 100.0)
            print("\t".join(out_rec), file=out_f)

    return File(out_path)


@task()
def plot_barcode_yields(barcode_yield_summary: File) -> File:
    data_dir = os.path.dirname(barcode_yield_summary.path)
    _ = run_catching_stderr(
        [
            "barcode_yields_plots.R",
            f"datafolder={data_dir}",
        ]
    )

    out_path = os.path.join(data_dir, "barcode_yields.jpg")

    return existing_file(out_path)
