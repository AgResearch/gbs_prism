import logging
import os.path
import subprocess

logger = logging.getLogger(__name__)


def fastqc(in_path: str, out_dir: str, num_threads: int = 8):
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(
        out_dir,
        "%s_fastqc.log"
        % os.path.basename(in_path).removesuffix(".gz").removesuffix(".fastq"),
    )
    with open(log_path, "w") as log_f:
        _ = subprocess.run(
            [
                "fastqc",
                "-t",
                str(num_threads),
                "-o",
                out_dir,
                in_path,
            ],
            check=True,
            stdout=log_f,
            stderr=log_f,
        )
