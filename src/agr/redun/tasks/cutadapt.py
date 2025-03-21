import logging
import os.path
from redun import task, File

from agr.redun.cluster_executor import run_job_1, Job1Spec
from agr.redun import one_forall

logger = logging.getLogger(__name__)

CUTADAPT_TOOL_NAME = "cutadapt"

# adapter phrase taken from
# https://github.com/AgResearch/gbs_prism/blob/dc5a71a6a2c554cd8952614d151a46ddce6892d1/ag_gbs_qc_prism.sh#L292
#
# the first 6 from an empirical assembly of recent data which matched
# Illumina NlaIII Gex Adapter 2.02 1885 TCGTATGCCGTCTTCTGCTTG
# Illumina DpnII Gex Adapter 2.01 1885 TCGTATGCCGTCTTCTGCTTG
# Illumina Small RNA 3p Adapter 1 1869 ATCTCGTATGCCGTCTTCTGCTTG
# Illumina Multiplexing Adapter 1 1426 GATCGGAAGAGCACACGTCT
# Illumina Universal Adapter 1423 AGATCGGAAGAG
# Illumina Multiplexing Index Sequencing Primer 1337 GATCGGAAGAGCACACGTCTGAACTCCAGTCAC
_ADAPTERS = [
    "TCGTATGCCGTCTTCTGCTTG",
    "TCGTATGCCGTCTTCTGCTTG",
    "ATCTCGTATGCCGTCTTCTGCTTG",
    "GATCGGAAGAGCACACGTCT",
    "GATCGGAAGAGCACACGTCT",
    "AGATCGGAAGAG",
    "GATCGGAAGAGCACACGTCTGAACTCCAGTCAC",
    "AGATCGGAAGAGCGGTTCAGCAGGAATGCCGAGACCGATCTCGTATGCCGTCTTCTGCTT",
    "AGATCGGAAGAG",
    "GATCGGAAGAGCACACGTCT",
    "GATCGGAAGAGCACACGTCTGAACTCCAGTCAC",
]


def _cutadapt_job_spec(in_path: str, out_path: str) -> Job1Spec:
    err_path = "%s.report" % out_path.removesuffix(".fastq")
    return Job1Spec(
        tool=CUTADAPT_TOOL_NAME,
        args=[
            "cutadapt",
        ]
        + [arg for adapter in _ADAPTERS for arg in ["-a", adapter]]
        + [
            in_path,
        ],
        stdout_path=out_path,
        stderr_path=err_path,
        expected_path=out_path,
    )


@task
def cutadapt_one(fastq_file: File, out_dir: str) -> File:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir,
        "%s.trimmed.fastq" % os.path.basename(fastq_file.path).removesuffix(".fastq"),
    )
    return run_job_1(
        _cutadapt_job_spec(in_path=fastq_file.path, out_path=out_path),
    )


@task()
def cutadapt_all(fastq_files: list[File], out_dir: str) -> list[File]:
    return one_forall(cutadapt_one, fastq_files, out_dir=out_dir)
