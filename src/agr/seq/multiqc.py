import logging
import os.path

from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


def multiqc(in_path: str, out_dir: str, run : str):
    """Generate a MultiQC report from a directory of FastQC reports.

    Args:
        in_path (str): Input directory of FastQC reports.
        out_dir (str): Output dieectory for the MultiQC.
        run (str): Input run name for the MultiQC report naming.
    """
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(
        out_dir,
        "%s_multiqc.log"
        % os.path.basename(in_path).removesuffix(".gz").removesuffix(".fastq"),
    )

    out_report = os.path.join(
        out_dir,
        run + "_multiqc.html"
        )

    with open(log_path, "w") as log_f:
        _ = run_catching_stderr(
            [
                "multiqc",
                "--interactive",
                "--force"
                "--outdir",
                out_dir,
                "--filename",
                out_report,
                in_path,
            ],
            check=True,
            stdout=log_f,
            stderr=log_f,
        )
