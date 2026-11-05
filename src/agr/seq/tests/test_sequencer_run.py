"""Tests for the MGI run directory.

Stdlib-only, so these run in CI.

`validate` fails fast on a run that is obviously not ready; `wait_until_stable` waits
out a copy still in progress. Its sleeps are replaced here by a fake that mutates the
files between snapshots, so nothing actually waits.
"""

import logging
import os

import pytest

from agr.seq.sequencer_run import SequencerRun, SequencerRunError, find_seq_root

RUN = "DL100018469"
LANES = [1, 2, 3, 4]


def _make_run(tmp_path, lanes=LANES, fastq_lanes=None, reads=("read",)):
    """Build an MGI run tree: <seq_root>/<run>/L0n.

    `reads` are the fastq name suffixes per lane: `("read",)` for single-end,
    `("read_1", "read_2")` for paired-end.
    """
    seq_root = tmp_path / "INV-MGI-T1"
    run_dir = seq_root / RUN
    fastq_lanes = lanes if fastq_lanes is None else fastq_lanes

    for lane in lanes:
        (run_dir / ("L%02d" % lane)).mkdir(parents=True)
    for lane in fastq_lanes:
        for read in reads:
            _ = (
                run_dir / ("L%02d" % lane) / ("%s_L%02d_%s.fq.gz" % (RUN, lane, read))
            ).write_bytes(b"x" * 32)

    return str(seq_root)


def test_run_directory_is_seq_root_joined_with_the_run_name(tmp_path):
    """seq_root points at the *instrument* directory, so this plain join still works.

    MGI nests runs three levels below run_data (<run_data>/T1+/INV-MGI-T1/<flowcell>)
    where Illumina runs sat flat, so pointing seq_root at the instrument keeps this a
    context-file change rather than a code change.
    """
    seq_root = _make_run(tmp_path)
    run = SequencerRun(seq_root, RUN)
    assert run.dir.endswith("INV-MGI-T1/%s" % RUN)
    assert run.name == RUN


def test_lane_paths(tmp_path):
    seq_root = _make_run(tmp_path)
    run = SequencerRun(seq_root, RUN)
    assert run.lane_dir(1).endswith("%s/L01" % RUN)
    [fastq] = run.lane_fastqs(1)
    assert fastq.endswith("L01/%s_L01_read.fq.gz" % RUN)



def test_validate_accepts_a_complete_run(tmp_path):
    seq_root = _make_run(tmp_path)
    SequencerRun(seq_root, RUN).validate(lanes=LANES)  # must not raise


def test_validate_names_the_lanes_that_are_not_ready(tmp_path):
    """Fails fast and legibly rather than surfacing from deep inside splitBarcode."""
    seq_root = _make_run(tmp_path, fastq_lanes=[1, 2])
    run = SequencerRun(seq_root, RUN)
    with pytest.raises(SequencerRunError, match="L03"):
        run.validate(lanes=LANES)


def test_validate_rejects_a_paired_end_run(tmp_path):
    """gbs_prism is single-end only, so a PE run is refused before any Slurm job."""
    seq_root = _make_run(tmp_path, reads=("read_1", "read_2"))
    run = SequencerRun(seq_root, RUN)
    with pytest.raises(SequencerRunError, match="L01: run is paired-end") as e:
        run.validate(lanes=LANES)
    assert "single-end runs only" in str(e.value)
    assert "L04" in str(e.value)


def test_validate_rejects_half_a_paired_end_pair(tmp_path):
    seq_root = _make_run(tmp_path, reads=("read_1",))
    run = SequencerRun(seq_root, RUN)
    with pytest.raises(SequencerRunError, match="L01"):
        run.validate(lanes=LANES)


def test_missing_run_directory_is_an_error(tmp_path):
    with pytest.raises(SequencerRunError):
        _ = SequencerRun(str(tmp_path), "NO_SUCH_RUN")


class _FakeSleep:
    """Stands in for `time.sleep`, running `on_sleep(n)` for the nth call (from 1)."""

    def __init__(self, on_sleep=None):
        self.calls = 0
        self._on_sleep = on_sleep

    def __call__(self, _seconds):
        self.calls += 1
        if self._on_sleep is not None:
            self._on_sleep(self.calls)


def _install(monkeypatch, fake):
    monkeypatch.setattr("agr.seq.sequencer_run.time.sleep", fake)


def _fastq(seq_root, lane=1):
    return os.path.join(
        seq_root, RUN, "L%02d" % lane, "%s_L%02d_read.fq.gz" % (RUN, lane)
    )


def _grow(path, n):
    """Append to `path`, setting an explicit mtime so the test does not depend on
    the filesystem's timestamp resolution."""
    with open(path, "ab") as f:
        _ = f.write(b"y")
    os.utime(path, ns=(n * 10**9, n * 10**9))


def test_wait_returns_after_one_interval_when_files_are_stable(tmp_path, monkeypatch):
    seq_root = _make_run(tmp_path)
    fake = _FakeSleep()
    _install(monkeypatch, fake)
    SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)
    assert fake.calls == 1


def test_wait_polls_until_a_growing_file_settles(tmp_path, monkeypatch):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=3)
    fake = _FakeSleep(lambda n: _grow(fastq, n) if n <= 2 else None)
    _install(monkeypatch, fake)
    SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)
    assert fake.calls == 3


def test_wait_treats_an_mtime_change_at_the_same_size_as_unstable(
    tmp_path, monkeypatch
):
    """A preallocating copy has its final size from the start, so size alone is not
    enough."""
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root)

    def rewrite(n):
        if n == 1:
            with open(fastq, "r+b") as f:
                _ = f.write(b"z")
            os.utime(fastq, ns=(10**9, 10**9))

    fake = _FakeSleep(rewrite)
    _install(monkeypatch, fake)
    SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)
    assert fake.calls == 2



def test_wait_treats_an_unreadable_file_as_not_ready(tmp_path, monkeypatch):
    """The SMB copy's share-mode lock shows up as EACCES on open, not in stat."""
    seq_root = _make_run(tmp_path)
    locked = _fastq(seq_root, lane=2)
    fake = _FakeSleep()
    _install(monkeypatch, fake)

    real_open = open

    def open_locked_until_second_sleep(path, *args, **kwargs):
        if path == locked and fake.calls < 2:
            raise PermissionError(13, "Permission denied", path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", open_locked_until_second_sleep)
    SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)
    assert fake.calls == 2


def test_wait_gives_up_after_max_wait_naming_the_unsettled_file(
    tmp_path, monkeypatch
):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=4)
    _install(monkeypatch, _FakeSleep(lambda n: _grow(fastq, n)))
    with pytest.raises(SequencerRunError, match="L04_read.fq.gz: size 32 -> 33"):
        SequencerRun(seq_root, RUN).wait_until_stable(
            lanes=LANES, interval_s=300, max_wait_s=0
        )


def test_wait_logs_tiered_stubs_before_probing(tmp_path, monkeypatch, caplog):
    """A migrated file is recalled by the open probe, which can take many minutes, so
    the log must say so rather than look hung."""
    seq_root = _make_run(tmp_path)
    stub = _fastq(seq_root, lane=2)
    real_stat = os.stat

    def stat_with_stub(path, *args, **kwargs):
        st = real_stat(path, *args, **kwargs)
        if path != stub:
            return st
        # Size and mtime stay unchanged so the snapshots agree; only blocks differ.
        fields = list(st)
        extra = {
            name: getattr(st, name)
            for name in ("st_atime", "st_mtime", "st_ctime")
            + ("st_atime_ns", "st_mtime_ns", "st_ctime_ns")
        }
        extra["st_blocks"] = 0
        extra["st_blksize"] = st.st_blksize
        return os.stat_result(fields[:10], extra)

    monkeypatch.setattr("agr.seq.sequencer_run.os.stat", stat_with_stub)
    _install(monkeypatch, _FakeSleep())
    with caplog.at_level(logging.INFO, logger="agr.seq.sequencer_run"):
        SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)

    assert "checking all 4 can be opened" in caplog.text
    assert "1 fastq(s) are on tiered storage" in caplog.text
    assert stub in caplog.text


def test_wait_does_not_report_resident_files_as_tiered(tmp_path, monkeypatch, caplog):
    seq_root = _make_run(tmp_path)
    _install(monkeypatch, _FakeSleep())
    with caplog.at_level(logging.INFO, logger="agr.seq.sequencer_run"):
        SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)

    assert "checking all 4 can be opened" in caplog.text
    assert "tiered storage" not in caplog.text


# --- find_seq_root: which of several instrument directories holds the run ---


def _roots(tmp_path, *names):
    roots = []
    for name in names:
        root = tmp_path / name
        root.mkdir(parents=True)
        roots.append(root)
    return roots


def test_find_seq_root_returns_the_root_holding_the_run(tmp_path):
    old, new = _roots(tmp_path, "old", "new")
    (new / RUN).mkdir()
    assert find_seq_root([str(old), str(new)], RUN) == str(new)


def test_find_seq_root_lists_every_root_searched_when_absent(tmp_path):
    old, new = _roots(tmp_path, "old", "new")
    with pytest.raises(SequencerRunError) as e:
        _ = find_seq_root([str(old), str(new)], RUN)
    assert str(old) in str(e.value) and str(new) in str(e.value)


def test_find_seq_root_prefers_the_first_root_for_a_symlinked_run(tmp_path):
    """A run symlinked into an earlier root is one run, not two: the first root wins,
    so a run already processed under that root keeps its seq_root (and its cache)."""
    old, new = _roots(tmp_path, "old", "new")
    (new / RUN).mkdir()
    (old / RUN).symlink_to(new / RUN)
    assert find_seq_root([str(old), str(new)], RUN) == str(old)


def test_find_seq_root_sees_through_differently_spelled_symlink_targets(tmp_path):
    """eRI reaches the same directory as /projects, /agr/persist and /mnt/gpfs/persist."""
    old, new = _roots(tmp_path, "old", "real/new")
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path / "real")
    (new / RUN).mkdir()
    (old / RUN).symlink_to(alias / "new" / RUN)
    assert find_seq_root([str(old), str(alias / "new")], RUN) == str(old)


def test_find_seq_root_refuses_to_guess_between_distinct_copies(tmp_path):
    old, new = _roots(tmp_path, "old", "new")
    (old / RUN).mkdir()
    (new / RUN).mkdir()
    with pytest.raises(SequencerRunError, match="ambiguous"):
        _ = find_seq_root([str(old), str(new)], RUN)


def test_find_seq_root_ignores_suffixed_copies(tmp_path):
    old, new = _roots(tmp_path, "old", "new")
    (old / (RUN + "_corrupt")).mkdir()
    (new / RUN).mkdir()
    assert find_seq_root([str(old), str(new)], RUN) == str(new)
