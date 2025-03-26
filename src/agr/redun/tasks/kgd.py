import logging
import os.path
from dataclasses import dataclass
from redun import task, File

from agr.redun.cluster_executor import run_job_n, JobNSpec

logger = logging.getLogger(__name__)

# keys for files, not filenames
KGD_SAMPLE_STATS = "sample-stats"
KGD_GUSBASE_RDATA = "gusbase-rdata"

KGD_TOOL_NAME = "KGD"


def _primary_hap_map_path(all_hapmap_paths: list[str]) -> str:
    hapmap_candidates = ["HapMap.hmc.txt.blinded", "HapMap.hmc.txt"]
    for hapmap_candidate in hapmap_candidates:
        for hapmap_path in all_hapmap_paths:
            if os.path.basename(hapmap_path) == hapmap_candidate:
                return hapmap_path

    assert False, "failed to find any of %s in %s" % (
        ", ".join(hapmap_candidates),
        ", ".join(all_hapmap_paths),
    )


def _kgd_job_spec(
    out_dir: str,
    hapmap_path: str,
    genotyping_method: str,
) -> JobNSpec:
    out_path = "%s.stdout" % out_dir
    err_path = "%s.stderr" % out_dir

    return JobNSpec(
        tool=KGD_TOOL_NAME,
        args=["run_kgd.R", hapmap_path, genotyping_method],
        stdout_path=out_path,
        stderr_path=err_path,
        cwd=out_dir,
        expected_paths={
            KGD_SAMPLE_STATS: os.path.join(out_dir, "SampleStats.csv"),
            KGD_GUSBASE_RDATA: os.path.join(out_dir, "GUSbase.RData"),
        },
        expected_globs={},
    )


@dataclass
class KgdOutput:
    sample_stats_csv: File
    gusbase_rdata: File


@task()
def _get_primary_hap_map_file(hap_map_files: list[File]) -> File:
    return File(
        _primary_hap_map_path([hap_map_file.path for hap_map_file in hap_map_files])
    )


def kgd_dir(work_dir: str) -> str:
    return os.path.join(work_dir, "KGD")


@task()
def kgd(work_dir: str, genotyping_method: str, hap_map_files: list[File]) -> KgdOutput:
    out_dir = kgd_dir(work_dir)
    hapmap_dir = os.path.join(work_dir, "hapMap")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(hapmap_dir, exist_ok=True)

    result_files = run_job_n(
        _kgd_job_spec(
            out_dir=out_dir,
            hapmap_path=_get_primary_hap_map_file(hap_map_files).path,
            genotyping_method=genotyping_method,
        ),
    )

    return KgdOutput(
        sample_stats_csv=result_files.expected_files[KGD_SAMPLE_STATS],
        gusbase_rdata=result_files.expected_files[KGD_GUSBASE_RDATA],
    )
