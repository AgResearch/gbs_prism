import logging
import os.path

from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


def multiqc(fastqc_in_path: str, bclconvert_in_path: str, out_dir: str, run : str): #TODO pass inputs as lists?
    """
    Generate a MultiQC report from FastQC and BCLConvert reports.

    Args:
        fastqc_in_path (str): Input top level directory of FastQC reports.
        bclconvert_in_path (str): Input top level directory of BCLConvert reports.
        out_dir (str): Output directory for the MultiQC report.
        run (str): Input run name for the MultiQC report naming.
    """
    os.makedirs(out_dir, exist_ok=True)

    log_path = os.path.join(
        out_dir,
        run + "_multiqc.log"
    )

    out_report = os.path.join(
        out_dir,
        run + "_multiqc_report.html"
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
                bclconvert_in_path,
                fastqc_in_path,
            ],
            check=True,
            stdout=log_f,
            stderr=log_f,
        )
