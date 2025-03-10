import logging
import os.path
from typing import List

from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


def multiqc(fastqc_in_paths: List[str], bclconvert_in_path: str, out_dir: str, out_path: str): #TODO arguments for each bclconvert report
    """
    Generate a MultiQC report from FastQC and BCLConvert reports.

    Args:
        fastqc_in_path (str): Input top level directory of FastQC reports.
        bclconvert_in_path (str): Input top level directory of BCLConvert reports.
        out_dir (str): Output directory for the MultiQC report.
        run (str): Input run name for the MultiQC report naming.
    """
    log_path = out_path.removesuffix(".html") + ".log"

    out_report = out_path

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
                bclconvert_in_path] + #TODO add arguments for each bclconvert report
                fastqc_in_paths
            ,
            check=True,
            stdout=log_f,
            stderr=log_f,
        )
