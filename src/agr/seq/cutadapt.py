import logging

import agr.util.cluster as cluster


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


def cutadapt_job_spec(in_path: str, out_path: str) -> cluster.Job1Spec:
    err_path = "%s.report" % out_path.removesuffix(".fastq")
    return cluster.Job1Spec(
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
