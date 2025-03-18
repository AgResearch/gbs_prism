import logging
import os.path

from typing import List

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

# keys for files, not filenames
KGD_SAMPLE_STATS = "sample-stats"
KGD_GUSBASE_RDATA = "gusbase-rdata"

KGD_TOOL_NAME = "KGD"


def primary_hap_map_path(all_hapmap_paths: List[str]) -> str:
    hapmap_candidates = ["HapMap.hmc.txt.blinded", "HapMap.hmc.txt"]
    for hapmap_candidate in hapmap_candidates:
        for hapmap_path in all_hapmap_paths:
            if os.path.basename(hapmap_path) == hapmap_candidate:
                return hapmap_candidate

    assert False, "failed to find any of %s in %s" % (
        ", ".join(hapmap_candidates),
        ", ".join(all_hapmap_paths),
    )


def kgd_job_spec(
    out_dir: str,
    hapmap_path: str,
    genotyping_method: str,
) -> cluster.JobNSpec:
    out_path = "%s.stdout" % out_dir
    err_path = "%s.stderr" % out_dir

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
