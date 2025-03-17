import logging
import os.path

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

# keys for files, not filenames
KGD_SAMPLE_STATS = "sample-stats"
KGD_GUSBASE_RDATA = "gusbase-rdata"

KGD_TOOL_NAME = "KGD"


def kgd_job_spec(
    out_dir: str,
    hapmap_dir: str,
    genotyping_method: str,
) -> cluster.JobNSpec:
    out_path = "%s.stdout" % out_dir
    err_path = "%s.stderr" % out_dir

    hapmap_files = ["HapMap.hmc.txt.blinded", "HapMap.hmc.txt"]
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

    return cluster.JobNSpec(
        tool=KGD_TOOL_NAME,
        args=["run_kgd.R", hapmap_path, genotyping_method],
        stdout_path=out_path,
        stderr_path=err_path,
        expected_paths={
            KGD_SAMPLE_STATS: os.path.join(out_dir, "SampleStats.csv"),
            KGD_GUSBASE_RDATA: os.path.join(out_dir, "GUSbase.RData"),
        },
        expected_globs={},
    )
