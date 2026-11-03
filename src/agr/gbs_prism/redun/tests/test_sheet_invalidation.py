"""Regression test for sample-sheet invalidation (CLAUDE.md backlog #0).

This mirrors the stage 1 nesting with stub tasks:
- `main(str)` -> `get_sheet(str) -> File` -> `stage1(File)`;
- `stage1` parses the sheet eagerly and passes value keys to children;
- the children are `demux` (keyed on the sheet without `[GenerateKeyfile]`) and a
  serialised per-library keyfile import keyed on `(library rows, [Data] rows)`.

It uses the real `agr.seq.mgi.sample_sheet` helpers stage 1 uses, and counts stub
executions to assert which edits re-run what.

Needs redun, so it is skipped under CI (`nix run '.#tests'`), which has none.
"""

import os.path
import shutil
from typing import Optional

import pytest

redun = pytest.importorskip("redun")

from redun import File, Scheduler, task  # noqa: E402
from redun.config import Config  # noqa: E402

from agr.seq.mgi.sample_sheet import (  # noqa: E402
    GENERATE_KEYFILE_SECTION,
    MgiSampleSheet,
    data_rows,
    gbs_library_specs,
    read_sample_sheet,
    without_sections,
)

redun_namespace = "agr.gbs_prism.tests.sheet_invalidation"

RUN = "DL100018469"
REFERENCE_SHEET = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "seq", "mgi", "tests", "%s.csv" % RUN
)


def _log(log_dir: str, what: str):
    with open(os.path.join(log_dir, "log.txt"), "a") as f:
        _ = f.write(what + "\n")


@task()
def get_sheet(root: str, run: str) -> File:
    return File(os.path.join(root, "%s.csv" % run))


@task()
def demux(sheet: MgiSampleSheet, log_dir: str) -> File:
    _log(log_dir, "demux")
    path = os.path.join(log_dir, "demux.txt")
    with open(path, "w") as f:
        _ = f.write(repr(sheet.data))
    return File(path)


@task()
def keyfile(
    library: str,
    library_rows: list[list[str]],
    data_rows: list[list[str]],
    merged: File,
    log_dir: str,
) -> File:
    _ = (library_rows, data_rows, merged)
    _log(log_dir, "keyfile %s" % library)
    path = os.path.join(log_dir, "%s.key" % library)
    with open(path, "w") as f:
        _ = f.write(repr(library_rows))
    return File(path)


@task(cache=False)
def sequenced_import(
    prev: Optional[File],
    library: str,
    library_rows: list[list[str]],
    data_rows: list[list[str]],
    merged: File,
    log_dir: str,
) -> File:
    _ = prev
    return keyfile(library, library_rows, data_rows, merged, log_dir)


@task()
def keyfiles(
    specs: dict[str, list[list[str]]],
    data_rows: list[list[str]],
    merged: File,
    log_dir: str,
) -> dict[str, File]:
    results = {}
    prev: Optional[File] = None
    for library, rows in specs.items():
        prev = results[library] = sequenced_import(
            prev, library, rows, data_rows, merged, log_dir
        )
    return results


@task()
def stage1(sample_sheet: File, log_dir: str) -> dict:
    _log(log_dir, "stage1")
    sheet = read_sample_sheet(sample_sheet.path)
    demuxed = demux(without_sections(sheet, [GENERATE_KEYFILE_SECTION]), log_dir)
    return {
        "demux": demuxed,
        "keyfiles": keyfiles(gbs_library_specs(sheet), data_rows(sheet), demuxed, log_dir),
    }


@task()
def main(root: str, run: str, log_dir: str) -> dict:
    return stage1(get_sheet(root, run), log_dir)


ALL_KEYFILES = ["keyfile SQ5420", "keyfile SQ5421", "keyfile SQ5575", "keyfile SQ5576"]


@pytest.fixture
def harness(tmp_path):
    sheets = tmp_path / "sheets"
    log_dir = tmp_path / "log"
    sheets.mkdir()
    log_dir.mkdir()
    sheet = sheets / ("%s.csv" % RUN)
    _ = shutil.copyfile(REFERENCE_SHEET, sheet)

    scheduler = Scheduler(
        config=Config(
            {"backend": {"db_uri": "sqlite:///%s" % (tmp_path / "redun.db")}}
        )
    )
    scheduler.load()

    def run() -> list[str]:
        log = log_dir / "log.txt"
        log.write_text("")
        _ = scheduler.run(main(str(sheets), RUN, str(log_dir)))
        return sorted(line for line in log.read_text().splitlines() if line)

    def edit(old: str, new: str):
        content = sheet.read_text()
        assert content.count(old) == 1, old
        _ = sheet.write_text(content.replace(old, new))

    first = run()
    assert first == sorted(["stage1", "demux"] + ALL_KEYFILES)
    return run, edit, sheet


def test_unchanged_sheet_is_a_full_cache_hit(harness):
    run, _, _ = harness
    assert run() == []


def test_touch_reparses_but_reruns_nothing(harness):
    run, _, sheet = harness
    stat = sheet.stat()
    os.utime(sheet, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
    assert run() == ["stage1"]


def test_generate_keyfile_edit_reimports_only_that_library(harness):
    run, edit, _ = harness
    edit(
        "SQ5421,13441,GENOMNZ,384,PstI,220-340",
        "SQ5421,13441,GENOMNZ,384,PstI,200-340",
    )
    assert run() == ["keyfile SQ5421", "stage1"]


def test_data_edit_redemultiplexes_and_reimports_every_library(harness):
    run, edit, _ = harness
    edit(
        "1,SQ5420,SQ5420_Deer_Goat_PstI,NS07,,,UDP0007,CTAGTGCTCT",
        "1,SQ5420,SQ5420_Deer_Goat_PstI,NS07,,,UDP0007,CTAGTGCTCA",
    )
    assert run() == sorted(["stage1", "demux"] + ALL_KEYFILES)


def test_non_barcode_data_edit_still_reimports_every_library(harness):
    """Description is read by gquery's import but never reaches the barcode file.

    The demux stub keys on the whole sheet minus [GenerateKeyfile], so it re-runs
    here too. In the real pipeline `split_barcodes_run` re-runs its checks, but each
    lane's `split_barcodes_one` stays cached because its barcode file is unchanged.
    """
    run, edit, _ = harness
    edit(
        "UDP0007,CTAGTGCTCT,Q5009,CCAACAGA,,SQ5420_Deer_Goat_PstI\n1,",
        "UDP0007,CTAGTGCTCT,Q5009,CCAACAGA,,SQ5420_edited\n1,",
    )
    assert run() == sorted(["stage1", "demux"] + ALL_KEYFILES)
