import logging
import os.path
import pdf2image

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

GUSBASE_TOOL_NAME = "GUSbase"


def gusbase_job_spec(GUSbase_RData_path: str) -> cluster.Job1Spec:
    work_dir = os.path.dirname(GUSbase_RData_path)
    base_path = os.path.join(work_dir, "GUSbase")
    stdout_path = "%s.stdout" % base_path
    stderr_path = "%s.stderr" % base_path

    return cluster.Job1Spec(
        tool=GUSBASE_TOOL_NAME,
        args=["run_GUSbase.R", GUSbase_RData_path],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        expected_path=os.path.join(work_dir, "Rplots.pdf"),
    )


def convert_GUSbase_output(GUSbase_out_path: str) -> str:
    work_dir = os.path.dirname(GUSbase_out_path)
    comet_pdf_path = os.path.join(work_dir, "GUSbase_comet.pdf")
    comet_jpg_path = os.path.join(work_dir, "GUSbase_comet.jpg")
    os.symlink(
        "Rplots.pdf",
        comet_pdf_path,
    )
    pages = pdf2image.convert_from_path(comet_pdf_path, 150)
    # we only expect 1 page
    pages[0].save(comet_jpg_path)
    return comet_jpg_path
