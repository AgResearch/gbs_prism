import logging
import os.path
from os.path import abspath
from dataclasses import dataclass
from redun import task, File
from typing import Optional

from redun_psij import (
    run_job_n_returning_failure,
    JobContext,
    JobNSpec,
    ExpectedPaths,
    ResultFiles,
)

logger = logging.getLogger(__name__)

KGD_STDOUT = "KGD.stdout"
KGD_STDERR = "KGD.stderr"

KGD_OUTPUT_PLOTS_REQUIRED = [
    "AlleleFreq.png",
    "CallRate.png",
    "Co-call-.png",
    "finplot.png",
    "Gcompare.png",
    "Gdiagdepth.png",
    "G-diag.png",
    "HWdisMAFsig.png",
    "LRT-hist.png",
    "LRT-QQ.png",
    "MAF.png",
    "SampDepthCR.png",
    "SampDepthHist.png",
    "SampDepth.png",
    "SampDepth-scored.png",
    "SNPCallRate.png",
    "SNPDepthHist.png",
    "SNPDepth.png",
    "X2star-QQ.png",
]

KGD_OUTPUT_PLOTS_OPTIONAL = [
    "ColourKeydepth.png",
    "G.splitdiagdepth.png",
    "InbCompare.png",
    "PlateDepth.png",
    "PlateInb.png",
    "SubplateDepth.png",
    "SubplateInb.png",
    "Co-call-HWdgm.05.png",
    "ColourKeyHWdgm.05heatmap.png",
    "GcompareHWdgm.05.png",
    "GHWdgm.05diagdepth.png",
    "GHWdgm.05-diag.png",
    "Heatmap-G5HWdgm.05.png",
    "MAFHWdgm.05.png",
    "PC1v2G5HWdgm.05.png",
    "PC1vDepthHWdgm.05.png",
    "PC1vInbHWdgm.05.png",
    "PCG5HWdgm.05.pdf",
]

KGD_OUTPUT_TEXT_FILES_REQUIRED = [
    "SampleStats.csv",
    "SampleStatsRawCombined.csv",
    "SampleStatsRaw.csv",
    "seqID.csv",
]

KGD_OUTPUT_TEXT_FILES_OPTIONAL = [
    "HighRelatedness.csv",
    "HighRelatedness.split.csv",
    "HeatmapOrderHWdgm.05.csv",
    "GHW05.csv",
    "GHW05-Inbreeding.csv",
    "GHW05-long.csv",
    "GHW05-pca_metadata.tsv",
    "GHW05-pca_vectors.tsv",
    "GHW05-PC.csv",
    "GHW05.vcf",
]

KGD_OUTPUT_BINARY_FILES_REQUIRED = [
    "GHW05.RData",
    "GUSbase.RData",
]

KGD_TOOL_NAME = "KGD"


def _kgd_job_spec(
    out_dir: str,
    hapmap_path: str,
    genotyping_method: str,
    job_context: JobContext,
) -> JobNSpec:
    out_path = "%s.stdout" % out_dir
    err_path = "%s.stderr" % out_dir

    return JobNSpec(
        tool=KGD_TOOL_NAME,
        args=["run_kgd.R", abspath(hapmap_path), genotyping_method],
        stdout_path=out_path,
        stderr_path=err_path,
        custom_attributes=job_context.custom_attributes,
        cwd=out_dir,
        expected_paths=ExpectedPaths(
            required={
                basename: os.path.join(out_dir, basename)
                for basename in KGD_OUTPUT_TEXT_FILES_REQUIRED
                + KGD_OUTPUT_BINARY_FILES_REQUIRED
                + KGD_OUTPUT_PLOTS_REQUIRED
            }
            | {
                KGD_STDOUT: out_path,
                KGD_STDERR: err_path,
            },
            optional={
                basename: os.path.join(out_dir, basename)
                for basename in KGD_OUTPUT_TEXT_FILES_OPTIONAL
                + KGD_OUTPUT_PLOTS_OPTIONAL
            },
        ),
    )


@dataclass
class KgdOutput:
    """
    The optional files are present if and only if `ok`.
    (Modelling this with inheritance is not a good fit with redun's lazy expressions.)
    """

    ok: bool
    plot_files: dict[str, File]
    text_files: dict[str, File]
    binary_files: dict[str, File]
    kgd_stdout: Optional[File]
    kgd_stderr: File

    @property
    def sample_stats_csv(self) -> Optional[File]:
        return self.text_files.get("SampleStats.csv")

    @property
    def gusbase_rdata(self) -> Optional[File]:
        return self.binary_files.get("GUSbase.RData")


def kgd_output_files(kgd_output: KgdOutput) -> list[File]:
    """Return all output except stderr as a list of files."""
    file_vars = vars(kgd_output).copy()
    del file_vars["ok"]
    del file_vars["kgd_stderr"]
    return [file for file in file_vars.values() if file is not None]


def kgd_dir(work_dir: str) -> str:
    return os.path.join(work_dir, "KGD")


@task()
def kgd(
    work_dir: str,
    hap_map_file: File,
    job_context: JobContext,
    genotyping_method: str = "default",
) -> KgdOutput:
    out_dir = kgd_dir(work_dir)
    hapmap_dir = os.path.join(work_dir, "hapMap")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(hapmap_dir, exist_ok=True)

    kgd_job_spec = _kgd_job_spec(
        out_dir=out_dir,
        hapmap_path=hap_map_file.path,
        genotyping_method=genotyping_method,
        job_context=job_context,
    )

    result = run_job_n_returning_failure(kgd_job_spec)

    if isinstance(result, ResultFiles):
        return KgdOutput(
            ok=True,
            text_files={
                basename: path
                for basename in (
                    KGD_OUTPUT_TEXT_FILES_REQUIRED + KGD_OUTPUT_TEXT_FILES_OPTIONAL
                )
                if (path := result.expected_files.get(basename)) is not None
            },
            binary_files={
                basename: result.expected_files[basename]
                for basename in KGD_OUTPUT_BINARY_FILES_REQUIRED
            },
            plot_files={
                basename: path
                for basename in (KGD_OUTPUT_PLOTS_REQUIRED + KGD_OUTPUT_PLOTS_OPTIONAL)
                if (path := result.expected_files.get(basename)) is not None
            },
            kgd_stdout=result.expected_files[KGD_STDOUT],
            kgd_stderr=result.expected_files[KGD_STDERR],
        )
    else:
        return KgdOutput(
            ok=False,
            text_files={},
            binary_files={},
            plot_files={},
            kgd_stdout=None,
            kgd_stderr=result.stderr,
        )
