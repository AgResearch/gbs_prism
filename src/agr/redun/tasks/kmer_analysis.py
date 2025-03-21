import logging
import os.path
from redun import task, File

from agr.redun.cluster_executor import run_job_1, Job1Spec
from agr.redun import one_forall
from agr.util.path import remove_if_exists

logger = logging.getLogger(__name__)

KMER_PRISM_TOOL_NAME = "kmer_prism"


def _kmer_analysis_job_spec(
    in_path: str,
    out_path: str,
    input_filetype: str,
    kmer_size: int,
    cwd: str,
) -> Job1Spec:
    log_path = "%s.log" % out_path.removesuffix(".1")

    return Job1Spec(
        tool=KMER_PRISM_TOOL_NAME,
        args=[
            "kmer_prism",
            "--input_filetype",
            input_filetype,
            "--kmer_size",
            str(kmer_size),
            "--output_filename",
            out_path,
            in_path,
            # this causes it to crash: 😩
            # assemble_low_entropy_kmers=True
        ],
        stdout_path=log_path,
        stderr_path=log_path,
        cwd=cwd,
        expected_path=out_path,
    )


@task()
def kmer_analysis_one(fastq_file: File, out_dir: str) -> File:
    """Run kmer analysis for a single fastq file."""
    kmer_prism_workdir = os.path.join(out_dir, "work")
    os.makedirs(kmer_prism_workdir, exist_ok=True)
    kmer_size = 6
    out_path = os.path.join(
        out_dir,
        "%s.k%d.1" % (os.path.basename(fastq_file.path), kmer_size),
    )
    remove_if_exists(out_path)

    return run_job_1(
        _kmer_analysis_job_spec(
            in_path=fastq_file.path,
            out_path=out_path,
            input_filetype="fasta",
            kmer_size=kmer_size,
            # kmer_prism drops turds in the current directory and doesn't pickup after itself,
            # so we run with cwd as a subdirectory of the output file
            cwd=kmer_prism_workdir,
        ),
    )


@task()
def kmer_analysis_all(fastq_files: list[File], out_dir: str) -> list[File]:
    """Run kmer analysis for multiple fastq files."""
    return one_forall(kmer_analysis_one, fastq_files, out_dir=out_dir)
