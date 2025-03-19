import logging
import os.path

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

FASTQC_TOOL_NAME = "fastqc"


def fastqc_job_spec(
    in_path: str, out_dir: str, num_threads: int = 8
) -> cluster.Job1Spec:
    basename = os.path.basename(in_path).removesuffix(".gz").removesuffix(".fastq")
    log_path = os.path.join(
        out_dir,
        "%s_fastqc.log"
        % os.path.basename(in_path).removesuffix(".gz").removesuffix(".fastq"),
    )
    out_path = os.path.join(out_dir, "%s%s" % (basename, "_fastqc.zip"))
    return cluster.Job1Spec(
        tool=FASTQC_TOOL_NAME,
        args=[
            "fastqc",
            "-t",
            str(num_threads),
            "-o",
            out_dir,
            in_path,
        ],
        stdout_path=log_path,
        stderr_path=log_path,
        cwd=out_dir,
        expected_path=out_path,
    )
