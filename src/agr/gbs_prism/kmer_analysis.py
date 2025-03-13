import logging

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

KMER_PRISM_TOOL_NAME = "kmer_prism"


def kmer_analysis_job_spec(
    in_path: str,
    out_path: str,
    input_filetype: str,
    kmer_size: int,
    cwd: str,
) -> cluster.Job1Spec:
    log_path = "%s.log" % out_path.removesuffix(".1")

    return cluster.Job1Spec(
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
