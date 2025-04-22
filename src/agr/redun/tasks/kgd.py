import logging
import os.path
from dataclasses import dataclass
from redun import task, File
from redun.scheduler import catch

from agr.redun.cluster_executor import ClusterExecutorError, run_job_n, JobNSpec

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
        },
        expected_globs={},
    )


@dataclass
class KgdOutput:
    pass

    def files(self) -> list[File]:
        raise NotImplementedError


@dataclass
class KgdOutputSuccess(KgdOutput):
    sample_stats_csv: File
    gusbase_rdata: File
    ghw05_csv: File
    ghw05_vcf: File
    ghw05_inbreeding_csv: File
    ghw05_long_csv: File
    ghw05_PC_csv: File
    ghw05_pca_metadata_tsv: File
    ghw05_pca_vectors_tsv: File
    heatmap_order_hwdgm05_csv: File
    high_relatedness_csv: File
    high_relateness_split_csv: File
    seq_ID_csv: File
    sample_stats_raw_csv: File
    sample_stats_raw_combined_csv: File
    kgd_stdout: File

    def files(self) -> list[File]:
        """Return all output as a list of files."""
        return [file for file in vars(self).values()]


@dataclass
class KgdOutputFailure(KgdOutput):
    kgd_stderr_text: str

    def kgd_output_files(self) -> list[File]:
        """On failure there are no output files."""
        return []


def kgd_output_files(kgd_output: KgdOutput) -> list[File]:
    """Return all output as a list of files."""

    return kgd_output.files()


@task()
def _get_primary_hap_map_file(hap_map_files: list[File]) -> File:
    return File(
        _primary_hap_map_path([hap_map_file.path for hap_map_file in hap_map_files])
    )


def kgd_dir(work_dir: str) -> str:
    return os.path.join(work_dir, "KGD")


@task()
def _kgd(
    work_dir: str, genotyping_method: str, hap_map_files: list[File]
) -> KgdOutputSuccess:
    out_dir = kgd_dir(work_dir)
    hapmap_dir = os.path.join(work_dir, "hapMap")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(hapmap_dir, exist_ok=True)

    kgd_job_spec = _kgd_job_spec(
        out_dir=out_dir,
        hapmap_path=_get_primary_hap_map_file(hap_map_files).path,
        genotyping_method=genotyping_method,
    )

    result_files = run_job_n(kgd_job_spec)

    return KgdOutputSuccess(
        sample_stats_csv=result_files.expected_files[KGD_SAMPLE_STATS],
        gusbase_rdata=result_files.expected_files[KGD_GUSBASE_RDATA],
        ghw05_csv=result_files.expected_files[GHW05_CSV],
        ghw05_vcf=result_files.expected_files[GHW05_VCF],
        ghw05_inbreeding_csv=result_files.expected_files[GHW05_INBREEDING_CSV],
        ghw05_long_csv=result_files.expected_files[GHW05_LONG_CSV],
        ghw05_PC_csv=result_files.expected_files[GHW05_PC_CSV],
        ghw05_pca_metadata_tsv=result_files.expected_files[GHW05_PCA_METADATA_TSV],
        ghw05_pca_vectors_tsv=result_files.expected_files[GHW05_PCA_VECTORS_TSV],
        heatmap_order_hwdgm05_csv=result_files.expected_files[
            HEATMAP_ORDER_HWDGM05_CSV
        ],
        high_relatedness_csv=result_files.expected_files[HIGH_RELATEDNESS_CSV],
        high_relateness_split_csv=result_files.expected_files[
            HIGH_RELATENESS_SPLIT_CSV
        ],
        seq_ID_csv=result_files.expected_files[SEQ_ID_CSV],
        sample_stats_raw_csv=result_files.expected_files[SAMPLE_STATS_RAW_CSV],
        sample_stats_raw_combined_csv=result_files.expected_files[
            SAMPLE_STATS_RAW_COMBINED_CSV
        ],
        kgd_stdout=result_files.expected_files[KGD_STDOUT],
    )


@task()
def recover_kgd_failure(e: ClusterExecutorError) -> KgdOutputFailure:
    if e.job_exit_code == 1 and e.job_stderr_text is not None:
        return KgdOutputFailure(kgd_stderr_text=e.job_stderr_text)
    else:
        raise e


@task()
def kgd(work_dir: str, genotyping_method: str, hap_map_files: list[File]) -> KgdOutput:
    return catch(
        _kgd(work_dir, genotyping_method, hap_map_files),
        ClusterExecutorError,
        recover_kgd_failure,
    )
