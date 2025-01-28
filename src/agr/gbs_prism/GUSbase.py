import logging
import os.path
import pdf2image

from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


def run_GUSbase(
    GUSbase_RData_path: str,
):
    work_dir = os.path.dirname(GUSbase_RData_path)
    base_path = os.path.join(work_dir, "GUSbase")
    out_path = "%s.stdout" % base_path

    run_GUSbase_command = ["run_GUSbase.R", GUSbase_RData_path]
    logger.info(" ".join(run_GUSbase_command))
    with open(out_path, "w") as out_f:
        _ = run_catching_stderr(
            run_GUSbase_command,
            cwd=work_dir,
            stdout=out_f,
            check=True,
        )

    os.rename(
        os.path.join(work_dir, "Rplots.pdf"),
        os.path.join(work_dir, "GUSbase_comet.pdf"),
    )
    pages = pdf2image.convert_from_path(
        os.path.join(work_dir, "GUSbase_comet.pdf"), 150
    )
    # we only expect 1 page
    pages[0].save(os.path.join(work_dir, "GUSbase_comet.jpg"))
