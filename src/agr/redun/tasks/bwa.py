import logging
import os.path
from dataclasses import dataclass
from redun import task, File

from agr.redun.cluster_executor import run_job_1, Job1Spec
from agr.redun import one_forall

logger = logging.getLogger(__name__)

BWA_ALN_TOOL_NAME = "bwa_aln"
BWA_SAMSE_TOOL_NAME = "bwa_samse"


class Bwa:
    def __init__(self, barcode_len: int):
        self._barcode_len = barcode_len

    @property
    def barcode_len(self) -> int:
        return self._barcode_len

    @property
    def moniker(self) -> str:
        return "B%d" % self._barcode_len


def _aln_job_spec(
    in_path: str, out_path: str, reference: str, barcode_len: int
) -> Job1Spec:
    return Job1Spec(
        tool=BWA_ALN_TOOL_NAME,
        args=[
            "bwa",
            "aln",
            "-B",
            str(barcode_len),
            reference,
            in_path,
        ],
        stdout_path=out_path,
        stderr_path=f"{out_path}.err",
        expected_path=out_path,
    )


def _samse_job_spec(
    sai_path: str, fastq_path: str, out_path: str, reference: str
) -> Job1Spec:
    return Job1Spec(
        tool=BWA_SAMSE_TOOL_NAME,
        args=[
            "bwa",
            "samse",
            reference,
            sai_path,
            fastq_path,
        ],
        stdout_path=out_path,
        stderr_path=f"{out_path}.err",
        expected_path=out_path,
    )


@dataclass
class BwaAlnOutput:
    fastq: File
    sai: File


@task()
def _bwa_aln_one(
    fastq_file: File, ref_name: str, ref_path: str, bwa: Bwa, out_dir: str
) -> BwaAlnOutput:
    """bwa aln for a single file with a single reference genome."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir,
        "%s.bwa.%s.%s.sai" % (os.path.basename(fastq_file.path), ref_name, bwa.moniker),
    )
    sai_file = run_job_1(
        _aln_job_spec(
            in_path=fastq_file.path,
            out_path=out_path,
            reference=ref_path,
            barcode_len=bwa.barcode_len,
        ),
    )
    return BwaAlnOutput(fastq=fastq_file, sai=sai_file)


@task()
def bwa_aln(
    fastq_files: list[File], ref_name: str, ref_path: str, bwa: Bwa, out_dir: str
) -> list[BwaAlnOutput]:
    """bwa aln for multiple files with a single reference genome."""
    return one_forall(
        _bwa_aln_one,
        fastq_files,
        ref_name=ref_name,
        ref_path=ref_path,
        bwa=bwa,
        out_dir=out_dir,
    )


@task()
def _bwa_samse_one(aln: BwaAlnOutput, ref_path: str) -> File:
    """bwa samse for a single file with a single reference genome."""
    out_path = "%s.bam" % aln.sai.path.removesuffix(".sai")
    return run_job_1(
        _samse_job_spec(
            sai_path=aln.sai.path,
            fastq_path=aln.fastq.path,
            out_path=out_path,
            reference=ref_path,
        ),
    )


@task()
def bwa_samse(alns: list[BwaAlnOutput], ref_path: str) -> list[File]:
    """bwa samse for multiple files."""
    return one_forall(
        _bwa_samse_one,
        alns,
        ref_path=ref_path,
    )
