import logging
import os.path
import subprocess
from itertools import islice

logger = logging.getLogger(__name__)


def run_kgd(
    cohort_str: str,
    base_dir: str,
    genotyping_method: str,
    hapmap_reldir: str = "hapMap",  # relative to base_dir
):
    engine = "KGD_tassel3"
    cohort_engine_path = os.path.join(base_dir, "%s.%s.KGD" % (cohort_str, engine))
    out_path = "%s.stdout" % cohort_engine_path
    err_path = "%s.stderr" % cohort_engine_path

    work_dir = os.path.join(base_dir, "KGD")
    os.makedirs(work_dir, exist_ok=True)

    hapmap_files = ["HapMap.hmc.txt.blinded", "HapMap.hmc.txt"]
    hapmap_dir = os.path.join(base_dir, hapmap_reldir)
    hapmap_paths = [
        hapmap_path
        for hapmap_file in hapmap_files
        if os.path.exists(hapmap_path := os.path.join(hapmap_dir, hapmap_file))
    ]

    assert hapmap_paths, "failed to find any of %s in %s" % (
        ", ".join(hapmap_files),
        hapmap_dir,
    )
    hapmap_path = hapmap_paths[0]

    if has_sufficient_snps(hapmap_path):
        with open(out_path, "w") as out_f:
            with open(err_path, "w") as err_f:
                run_kgd_command = ["run_kgd.R", hapmap_path, genotyping_method]
                logger.info(" ".join(run_kgd_command))
                _ = subprocess.run(
                    run_kgd_command,
                    cwd=work_dir,
                    stdout=out_f,
                    stderr=err_f,
                    check=True,
                )
    else:
        print("skipping KGD since insufficient SNPs in %s" % hapmap_path)


def has_sufficient_snps(hapmap_file: str):
    # KGD seems to fail badly with 0 or 1 SNP, so we need 2, plus the header line
    required_snps = 2
    with open(hapmap_file, "r") as f:
        return len(list(islice(f, required_snps + 1))) == required_snps + 1
