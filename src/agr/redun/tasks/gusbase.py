import logging
import os.path
import pdf2image
from redun import task, File

from agr.redun.cluster_executor import run_job_1, Job1Spec
from agr.util.path import symlink

logger = logging.getLogger(__name__)

GUSBASE_TOOL_NAME = "GUSbase"


def _gusbase_job_spec(gusbase_rdata_path: str) -> Job1Spec:
    work_dir = os.path.dirname(gusbase_rdata_path)
    base_path = os.path.join(work_dir, "GUSbase")
    stdout_path = "%s.stdout" % base_path
    stderr_path = "%s.stderr" % base_path

    return Job1Spec(
        tool=GUSBASE_TOOL_NAME,
        args=["run_GUSbase.R", gusbase_rdata_path],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        cwd=work_dir,
        expected_path=os.path.join(work_dir, "Rplots.pdf"),
    )


@task()
def _get_converted_GUSbase_output(gusbase_out_file: File) -> File:
    work_dir = os.path.dirname(gusbase_out_file.path)
    comet_pdf_path = os.path.join(work_dir, "GUSbase_comet.pdf")
    comet_jpg_path = os.path.join(work_dir, "GUSbase_comet.jpg")
    symlink("Rplots.pdf", comet_pdf_path, force=True)
    pages = pdf2image.convert_from_path(comet_pdf_path, 150)
    # we only expect 1 page
    pages[0].save(comet_jpg_path)
    return File(comet_jpg_path)


@task()
def gusbase(gusbase_rdata: File) -> File:
    return _get_converted_GUSbase_output(
        run_job_1(
            _gusbase_job_spec(gusbase_rdata.path),
        )
    )
