"""The MGI sample sheet as a redun `File`, so that editing it re-triggers stage 1.

The sheet lives outside the run tree at `<sample_sheet_root>/<run>.csv`. A path string
hides its content from redun, which then reuses every cached result after an edit.
Returning it as a `File` from a task makes the sheet's hash part of the call tree, so
an edit (or a `touch`) re-runs the consumer. Stage 1 then derives value keys from the
parsed sheet, which decide what actually re-runs (see `run_stage1`).

The Illumina branch counterpart is `await_run_complete`.
"""

import logging
import os.path

from redun import task, File

from agr.seq.mgi.sample_sheet import MgiSampleSheetError

redun_namespace = "agr.gbs_prism"

logger = logging.getLogger(__name__)


@task()
def get_sample_sheet(sample_sheet_root: str, run: str) -> File:
    """Return `<sample_sheet_root>/<run>.csv` as a `File`, to drive invalidation.

    Named `<run>.csv` because gquery cross-checks the filename stem against
    `[Header] Flowcell`.
    """
    path = os.path.join(sample_sheet_root, "%s.csv" % run)
    if not os.path.exists(path):
        raise MgiSampleSheetError("sample sheet does not exist: %s" % path)
    return File(path)


@task()
def archive_sample_sheet(sample_sheet: File, out_path: str) -> File:
    """Keep the run's own copy of the sheet it processed, refreshed on every edit.

    Copied only when the content differs, so the archive's mtime, and therefore its
    redun hash, is unchanged when the sheet is merely touched. This is the same
    reasoning as `write_barcode_file`.
    """
    with open(sample_sheet.path, "rb") as f:
        content = f.read()

    if os.path.exists(out_path):
        with open(out_path, "rb") as f:
            if f.read() == content:
                logger.debug("%s is unchanged, leaving it alone", out_path)
                return File(out_path)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        _ = f.write(content)
    return File(out_path)
