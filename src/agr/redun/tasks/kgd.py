import logging
import os.path
from dataclasses import dataclass
from redun import task, File
from typing import Optional

from agr.redun.cluster_executor import (
    run_job_n_returning_failure,
    ClusterExecutorJobFailure,
    JobNSpec,
    ResultFiles,
)

logger = logging.getLogger(__name__)

# keys for files, not filenames
KGD_SAMPLE_STATS = "sample-stats"
KGD_GUSBASE_RDATA = "gusbase-rdata"
GHW05_CSV = "ghw05-csv"
GHW05_VCF = "ghw05-vcf"
GHW05_INBREEDING_CSV = "ghw05-inbreeding-csv"
GHW05_LONG_CSV = "ghw05-long-csv"
GHW05_PC_CSV = "ghw05-pc-csv"
GHW05_PCA_METADATA_TSV = "ghw05-pca-metadata-tsv"
GHW05_PCA_VECTORS_TSV = "ghw05-pca-vectors-tsv"
HEATMAP_ORDER_HWDGM05_CSV = "heatmap-order-hwdgm05-csv"
HIGH_RELATEDNESS_CSV = "high-relatedness-csv"
HIGH_RELATENESS_SPLIT_CSV = "high-relateness-split-csv"
SEQ_ID_CSV = "seq-id-csv"
SAMPLE_STATS_RAW_CSV = "sample-stats-raw-csv"
SAMPLE_STATS_RAW_COMBINED_CSV = "sample-stats-raw-combined-csv"
KGD_STDOUT = "kgd-stdout"
KGD_STDERR = "kgd-stderr"

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
            GHW05_CSV: os.path.join(out_dir, "GHW05.csv"),
            GHW05_VCF: os.path.join(out_dir, "GHW05.vcf"),
            GHW05_INBREEDING_CSV: os.path.join(out_dir, "GHW05-Inbreeding.csv"),
            GHW05_LONG_CSV: os.path.join(out_dir, "GHW05-long.csv"),
            GHW05_PC_CSV: os.path.join(out_dir, "GHW05-PC.csv"),
            GHW05_PCA_METADATA_TSV: os.path.join(out_dir, "GHW05-pca_metadata.tsv"),
            GHW05_PCA_VECTORS_TSV: os.path.join(out_dir, "GHW05-pca_vectors.tsv"),
            HEATMAP_ORDER_HWDGM05_CSV: os.path.join(
                out_dir, "HeatmapOrderHWdgm.05.csv"
            ),
            HIGH_RELATEDNESS_CSV: os.path.join(out_dir, "HighRelatedness.csv"),
            HIGH_RELATENESS_SPLIT_CSV: os.path.join(
                out_dir, "HighRelatedness.split.csv"
            ),
            SEQ_ID_CSV: os.path.join(out_dir, "seqID.csv"),
            SAMPLE_STATS_RAW_CSV: os.path.join(out_dir, "SampleStatsRaw.csv"),
            SAMPLE_STATS_RAW_COMBINED_CSV: os.path.join(
                out_dir, "SampleStatsRawCombined.csv"
            ),
            KGD_STDOUT: out_path,
            KGD_STDERR: err_path,
        },
        expected_globs={},
    )


@dataclass
class KgdOutput:
    """
    The optional files are present if and only if `ok`.
    (Modelling this with inheritance is not a good fit with redun's lazy expressions.)
    """

    ok: bool
    sample_stats_csv: Optional[File]
    gusbase_rdata: Optional[File]
    ghw05_csv: Optional[File]
    ghw05_vcf: Optional[File]
    ghw05_inbreeding_csv: Optional[File]
    ghw05_long_csv: Optional[File]
    ghw05_PC_csv: Optional[File]
    ghw05_pca_metadata_tsv: Optional[File]
    ghw05_pca_vectors_tsv: Optional[File]
    heatmap_order_hwdgm05_csv: Optional[File]
    high_relatedness_csv: Optional[File]
    high_relateness_split_csv: Optional[File]
    seq_ID_csv: Optional[File]
    sample_stats_raw_csv: Optional[File]
    sample_stats_raw_combined_csv: Optional[File]
    kgd_stdout: Optional[File]
    kgd_stderr: File


def kgd_output_files(kgd_output: KgdOutput) -> list[File]:
    """Return all output except stderr as a list of files."""
    file_vars = vars(kgd_output)
    del file_vars["ok"]
    del file_vars["kgd_stderr"]
    return [file for file in file_vars.values() if file is not None]


@task()
def _get_primary_hap_map_file(hap_map_files: list[File]) -> File:
    return File(
        _primary_hap_map_path([hap_map_file.path for hap_map_file in hap_map_files])
    )


def kgd_dir(work_dir: str) -> str:
    return os.path.join(work_dir, "KGD")


@task()
def kgd_output(result: ResultFiles | ClusterExecutorJobFailure) -> KgdOutput:
    """Unwrap the lazy result expression and repackage the result files."""
    if isinstance(result, ResultFiles):
        return KgdOutput(
            ok=True,
            sample_stats_csv=result.expected_files[KGD_SAMPLE_STATS],
            gusbase_rdata=result.expected_files[KGD_GUSBASE_RDATA],
            ghw05_csv=result.expected_files[GHW05_CSV],
            ghw05_vcf=result.expected_files[GHW05_VCF],
            ghw05_inbreeding_csv=result.expected_files[GHW05_INBREEDING_CSV],
            ghw05_long_csv=result.expected_files[GHW05_LONG_CSV],
            ghw05_PC_csv=result.expected_files[GHW05_PC_CSV],
            ghw05_pca_metadata_tsv=result.expected_files[GHW05_PCA_METADATA_TSV],
            ghw05_pca_vectors_tsv=result.expected_files[GHW05_PCA_VECTORS_TSV],
            heatmap_order_hwdgm05_csv=result.expected_files[HEATMAP_ORDER_HWDGM05_CSV],
            high_relatedness_csv=result.expected_files[HIGH_RELATEDNESS_CSV],
            high_relateness_split_csv=result.expected_files[HIGH_RELATENESS_SPLIT_CSV],
            seq_ID_csv=result.expected_files[SEQ_ID_CSV],
            sample_stats_raw_csv=result.expected_files[SAMPLE_STATS_RAW_CSV],
            sample_stats_raw_combined_csv=result.expected_files[
                SAMPLE_STATS_RAW_COMBINED_CSV
            ],
            kgd_stdout=result.expected_files[KGD_STDOUT],
            kgd_stderr=result.expected_files[KGD_STDERR],
        )
    else:
        return KgdOutput(
            ok=False,
            sample_stats_csv=None,
            gusbase_rdata=None,
            ghw05_csv=None,
            ghw05_vcf=None,
            ghw05_inbreeding_csv=None,
            ghw05_long_csv=None,
            ghw05_PC_csv=None,
            ghw05_pca_metadata_tsv=None,
            ghw05_pca_vectors_tsv=None,
            heatmap_order_hwdgm05_csv=None,
            high_relatedness_csv=None,
            high_relateness_split_csv=None,
            seq_ID_csv=None,
            sample_stats_raw_csv=None,
            sample_stats_raw_combined_csv=None,
            kgd_stdout=None,
            kgd_stderr=result.stderr,
        )


@task()
def kgd(work_dir: str, genotyping_method: str, hap_map_files: list[File]) -> KgdOutput:
    out_dir = kgd_dir(work_dir)
    hapmap_dir = os.path.join(work_dir, "hapMap")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(hapmap_dir, exist_ok=True)

    kgd_job_spec = _kgd_job_spec(
        out_dir=out_dir,
        hapmap_path=_get_primary_hap_map_file(hap_map_files).path,
        genotyping_method=genotyping_method,
    )

    return kgd_output(run_job_n_returning_failure(kgd_job_spec))
