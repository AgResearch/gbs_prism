"""Tests for the MGI run directory.

`validate` fails fast on a run that is obviously not ready; `wait_until_stable` waits
out a copy still in progress. Its sleeps are replaced here by a fake that mutates the
files between snapshots, so nothing actually waits.
"""

import gzip
import hashlib
import logging
import os

import pytest

from agr.seq.sequencer_run import (
    SequencerRun,
    SequencerRunError,
    find_seq_root,
    read_file_info,
)

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
        info = []
        for read in reads:
            name = "%s_L%02d_%s.fq.gz" % (RUN, lane, read)
            content = _gz(lane, read)
            _ = (run_dir / ("L%02d" % lane) / name).write_bytes(content)
            info.append("%s  %s\n" % (hashlib.md5(content).hexdigest().upper(), name))
        _ = (
            run_dir / ("L%02d" % lane) / ("%s_L%02d_FileInfo.txt" % (RUN, lane))
        ).write_text("".join(info))
        paired = any(read.startswith("read_") for read in reads)
        _ = (run_dir / ("L%02d" % lane) / "BioInfo.csv").write_text(
            PE_BIOINFO if paired else SE_BIOINFO
        )

    return str(seq_root)


SE_BIOINFO = "Machine ID,INV-MGI-T1\nRead1Len,100\nRead2Len,0\nBarcodeLen,10\nDualBarcodeLen,8\n"
PE_BIOINFO = "Machine ID,INV-MGI-T1\nRead1Len,150\nRead2Len,150\nBarcodeLen,10\nDualBarcodeLen,8\n"


def _gz(lane, read):
    """A small real gzip fastq, distinct per file, with a fixed header mtime."""
    record = "@r%d_%s\nACGTACGTAC\n+\nIIIIIIIIII\n" % (lane, read)
    return gzip.compress(record.encode() * 4, mtime=0)


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


def _lane_file(seq_root, lane, name):
    return os.path.join(seq_root, RUN, "L%02d" % lane, name)


def test_validate_requires_bioinfo_before_any_wait(tmp_path):
    """BioInfo.csv lands before the fastq, so its absence is known at launch rather
    than after a copy wait of up to 24 h."""
    seq_root = _make_run(tmp_path)
    os.remove(_lane_file(seq_root, 2, "BioInfo.csv"))
    with pytest.raises(SequencerRunError, match="L02: .*no BioInfo.csv"):
        SequencerRun(seq_root, RUN).validate(lanes=LANES)


def test_validate_rejects_bioinfo_that_disagrees_with_the_fastqs(tmp_path):
    seq_root = _make_run(tmp_path)
    _ = open(_lane_file(seq_root, 3, "BioInfo.csv"), "w").write(PE_BIOINFO)
    with pytest.raises(
        SequencerRunError, match="L03: .*BioInfo.csv declares paired-end but the run "
        "directory holds a single fastq"
    ):
        SequencerRun(seq_root, RUN).validate(lanes=LANES)


def test_validate_requires_file_info_before_any_wait(tmp_path):
    seq_root = _make_run(tmp_path)
    os.remove(_lane_file(seq_root, 1, "%s_L01_FileInfo.txt" % RUN))
    with pytest.raises(SequencerRunError, match="L01: no .*L01_FileInfo.txt"):
        SequencerRun(seq_root, RUN).validate(lanes=LANES)


def test_validate_requires_each_fastq_to_be_listed_in_file_info(tmp_path):
    seq_root = _make_run(tmp_path)
    info = _lane_file(seq_root, 4, "%s_L04_FileInfo.txt" % RUN)
    _ = open(info, "w").write("%s  someone_else.fq.gz\n" % ("0" * 32))
    with pytest.raises(SequencerRunError, match="L04: .*L04_read.fq.gz is not listed"):
        SequencerRun(seq_root, RUN).validate(lanes=LANES)


def test_validate_reports_every_problem_together(tmp_path):
    seq_root = _make_run(tmp_path, fastq_lanes=[1, 2, 3])
    os.remove(_lane_file(seq_root, 1, "BioInfo.csv"))
    os.remove(_lane_file(seq_root, 2, "%s_L02_FileInfo.txt" % RUN))
    with pytest.raises(SequencerRunError) as e:
        SequencerRun(seq_root, RUN).validate(lanes=LANES)
    message = str(e.value)
    assert "L01: " in message and "BioInfo.csv" in message
    assert "L02: no " in message
    assert "L04: " in message  # no fastq at all


def test_missing_run_directory_is_an_error(tmp_path):
    with pytest.raises(SequencerRunError):
        _ = SequencerRun(str(tmp_path), "NO_SUCH_RUN")


class _FakeSleep:
    """Stands in for `time.sleep`, running `on_sleep(n)` for the nth call (from 1).

    Also the clock: `monotonic` advances only by the seconds slept, so idle and
    backstop durations are exact multiples of the interval.
    """

    def __init__(self, on_sleep=None):
        self.calls = 0
        self.now = 0.0
        self._on_sleep = on_sleep

    def __call__(self, seconds):
        self.calls += 1
        self.now += seconds
        if self._on_sleep is not None:
            self._on_sleep(self.calls)

    def monotonic(self):
        return self.now


def _install(monkeypatch, fake):
    monkeypatch.setattr("agr.seq.sequencer_run.time.sleep", fake)
    monkeypatch.setattr("agr.seq.sequencer_run.time.monotonic", fake.monotonic)


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
                _ = f.seek(12)
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
    with pytest.raises(SequencerRunError, match=r"L04_read.fq.gz: size \d+ -> \d+"):
        SequencerRun(seq_root, RUN).wait_until_stable(
            lanes=LANES, interval_s=300, max_wait_s=0
        )


def _fake_allocation(monkeypatch, path, fraction):
    """Make `os.stat` report `path` with `fraction` of its size allocated."""
    real_stat = os.stat

    def stat(p, *args, **kwargs):
        st = real_stat(p, *args, **kwargs)
        if p != path:
            return st
        # Size and mtime stay unchanged so the snapshots agree; only blocks differ.
        extra = {
            name: getattr(st, name)
            for name in ("st_atime", "st_mtime", "st_ctime")
            + ("st_atime_ns", "st_mtime_ns", "st_ctime_ns")
        }
        extra["st_blocks"] = int(st.st_size * fraction) // 512
        extra["st_blksize"] = st.st_blksize
        return os.stat_result(list(st)[:10], extra)

    monkeypatch.setattr("agr.seq.sequencer_run.os.stat", stat)


def _write_big_gzip(path, n_bytes=3 * 1024 * 1024):
    """An incompressible gzip bigger than the unallocated-slack threshold."""
    _ = open(path, "wb").write(gzip.compress(os.urandom(n_bytes), mtime=0))


def test_wait_logs_cold_stubs_before_probing(tmp_path, monkeypatch, caplog):
    """A migrated file is recalled by the open probe, which can take many minutes, so
    the log must say so rather than look hung."""
    seq_root = _make_run(tmp_path)
    stub = _fastq(seq_root, lane=2)
    _fake_allocation(monkeypatch, stub, 0.0)
    _install(monkeypatch, _FakeSleep())
    with caplog.at_level(logging.INFO, logger="agr.seq.sequencer_run"):
        SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)

    assert "checking all 4 can be opened" in caplog.text
    assert "1 fastq(s) are on the cold tier" in caplog.text
    assert stub in caplog.text


def test_wait_does_not_report_resident_files_as_cold(tmp_path, monkeypatch, caplog):
    seq_root = _make_run(tmp_path)
    _install(monkeypatch, _FakeSleep())
    with caplog.at_level(logging.INFO, logger="agr.seq.sequencer_run"):
        SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)

    assert "checking all 4 can be opened" in caplog.text
    assert "cold tier" not in caplog.text


def test_a_partly_allocated_stalled_copy_is_unfinished_not_cold(tmp_path, monkeypatch, caplog):
    """DL100022099 L02 on 6 Nov: 99% allocated, a stalled copy - once misreported as
    tiered storage."""
    seq_root = _make_run(tmp_path)
    partial = _fastq(seq_root, lane=2)
    _write_big_gzip(partial)
    _fake_allocation(monkeypatch, partial, 0.5)
    _install(monkeypatch, _FakeSleep())
    with caplog.at_level(logging.INFO, logger="agr.seq.sequencer_run"):
        with pytest.raises(SequencerRunError, match=r"L02_read.fq.gz: only 50.0% written"):
            SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)
    assert "cold tier" not in caplog.text


def test_wait_stops_on_a_stalled_non_gzip_start(tmp_path, monkeypatch):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=2)
    with open(fastq, "r+b") as f:
        _ = f.write(b"\x9b\x7a")
    _install(monkeypatch, _FakeSleep())
    with pytest.raises(SequencerRunError, match=r"L02_read.fq.gz: not gzip at start \(9b 7a\)"):
        SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)


def test_wait_stops_on_a_stalled_zero_tail(tmp_path, monkeypatch):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=3)
    with open(fastq, "ab") as f:
        _ = f.write(b"\0" * 64 * 1024)
    _install(monkeypatch, _FakeSleep())
    with pytest.raises(SequencerRunError, match=r"L03_read.fq.gz: last 64 KiB are all zero"):
        SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)


def test_a_stalled_copy_stops_after_stall_after_s_with_the_reason(tmp_path, monkeypatch):
    """DL100022099 L02/L04 on 6 Nov: unchanged since 09:30. Stop once nothing has
    been written for `stall_after_s`, rather than wait out the 24 h backstop - but not
    after a single quiet interval, which a transient SMB pause can produce."""
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=2)
    with open(fastq, "r+b") as f:
        _ = f.write(b"\x9b\x7a")
    fake = _FakeSleep()
    _install(monkeypatch, fake)
    with pytest.raises(SequencerRunError) as e:
        SequencerRun(seq_root, RUN).wait_until_stable(
            lanes=LANES, interval_s=300, stall_after_s=900
        )
    assert fake.calls == 3
    assert "copy stalled, nothing written to these fastqs in the last 15 min" in str(e.value)
    assert "L02_read.fq.gz: not gzip at start" in str(e.value)
    assert "Re-copy" in str(e.value)


def test_a_stall_that_resumes_before_the_threshold_keeps_waiting(
    tmp_path, monkeypatch, caplog
):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=2)
    good = open(fastq, "rb").read()
    with open(fastq, "r+b") as f:
        _ = f.write(b"\x9b\x7a")

    def resume(n):
        if n == 2:  # the copy comes back after 10 quiet minutes and completes
            _ = open(fastq, "wb").write(good)
            os.utime(fastq, ns=(5 * 10**9, 5 * 10**9))

    fake = _FakeSleep(resume)
    _install(monkeypatch, fake)
    with caplog.at_level(logging.INFO, logger="agr.seq.sequencer_run"):
        SequencerRun(seq_root, RUN).wait_until_stable(
            lanes=LANES, interval_s=300, stall_after_s=900
        )
    # 1: quiet and unfinished, under the threshold; 2: written to; 3: ready.
    assert fake.calls == 3
    assert "no progress for 5 min (stopping at 15 min if nothing is written)" in caplog.text


def _lock(monkeypatch, path, until=lambda: True):
    """Make `open(path)` fail as a copy's share lock does, while `until()` holds."""
    real_open = open

    def open_locked(p, *args, **kwargs):
        if p == path and until():
            raise PermissionError(13, "Permission denied", p)
        return real_open(p, *args, **kwargs)

    monkeypatch.setattr("builtins.open", open_locked)


def test_a_locked_copy_with_nothing_written_is_stopped_as_hung(tmp_path, monkeypatch):
    """A lock is evidence of a live copy - but not forever: locked with nothing
    written for `locked_idle_after_s` is a hung copier, not a 24 h wait."""
    seq_root = _make_run(tmp_path)
    _lock(monkeypatch, _fastq(seq_root, lane=1))
    fake = _FakeSleep()
    _install(monkeypatch, fake)
    with pytest.raises(SequencerRunError) as e:
        SequencerRun(seq_root, RUN).wait_until_stable(
            lanes=LANES, interval_s=300, stall_after_s=300, locked_idle_after_s=900
        )
    assert fake.calls == 3
    assert "nothing written for 15 min" in str(e.value)
    assert "may be hung" in str(e.value)
    assert "L01_read.fq.gz: " in str(e.value)


def test_a_stalled_lane_is_reported_while_another_is_locked(tmp_path, monkeypatch):
    """One lane's lock must not hide another lane's stalled copy."""
    seq_root = _make_run(tmp_path)
    _lock(monkeypatch, _fastq(seq_root, lane=1))
    stalled = _fastq(seq_root, lane=2)
    with open(stalled, "r+b") as f:
        _ = f.write(b"\x9b\x7a")
    _install(monkeypatch, _FakeSleep())
    with pytest.raises(SequencerRunError, match=r"copy stalled(.|\n)*L02_read.fq.gz: not gzip"):
        SequencerRun(seq_root, RUN).wait_until_stable(
            lanes=LANES, interval_s=300, stall_after_s=900, locked_idle_after_s=3600
        )


def test_a_recall_still_in_progress_is_not_a_stall(tmp_path, monkeypatch):
    """A cold-tier file whose recall has not completed when probed is partly
    allocated, like a stalled copy, but is no evidence of one."""
    seq_root = _make_run(tmp_path)
    cold = _fastq(seq_root, lane=2)
    _write_big_gzip(cold)
    fake = _FakeSleep()
    real_stat = os.stat
    probes = []

    def stat(p, *args, **kwargs):
        st = real_stat(p, *args, **kwargs)
        if p != cold:
            return st
        # Offline until probed; the recall then runs one interval past each probe.
        fraction = 0.0 if not probes else (0.5 if fake.calls < 4 else 1.0)
        extra = {
            name: getattr(st, name)
            for name in ("st_atime", "st_mtime", "st_ctime")
            + ("st_atime_ns", "st_mtime_ns", "st_ctime_ns")
        }
        extra["st_blocks"] = int(st.st_size * fraction) // 512
        extra["st_blksize"] = st.st_blksize
        return os.stat_result(list(st)[:10], extra)

    import agr.seq.sequencer_run as sr

    real_unreadable = sr._unreadable

    def unreadable(paths):
        probes.append(fake.calls)
        return real_unreadable(paths)

    monkeypatch.setattr("agr.seq.sequencer_run.os.stat", stat)
    monkeypatch.setattr("agr.seq.sequencer_run._unreadable", unreadable)
    _install(monkeypatch, fake)
    SequencerRun(seq_root, RUN).wait_until_stable(
        lanes=LANES, interval_s=300, stall_after_s=300
    )
    # 1: probed, recall half done -> waiting, not a stall even at stall_after_s=300;
    # 2: blocks moved -> progressing; 3: half done still -> waiting;
    # 4: recall done, blocks moved -> progressing; 5: ready.
    assert fake.calls == 5


def test_wait_resumes_when_an_unfinished_copy_completes(tmp_path, monkeypatch):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=1)
    good = open(fastq, "rb").read()
    _ = open(fastq, "wb").write(b"\0" * len(good))
    os.utime(fastq, ns=(10**9, 10**9))

    def copy(n):
        if n == 1:  # still copying: written to, still unfinished
            with open(fastq, "r+b") as f:
                _ = f.write(b"\0")
        elif n == 2:  # copy completes
            _ = open(fastq, "wb").write(good)
            os.utime(fastq, ns=(2 * 10**9, 2 * 10**9))

    fake = _FakeSleep(copy)
    _install(monkeypatch, fake)
    SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)
    # 1: written to but mtime pinned, unfinished -> wait; 2: completes (changed);
    # 3: stable and finished.
    assert fake.calls == 3


def test_a_live_preallocated_copy_is_not_mistaken_for_a_stall(tmp_path, monkeypatch):
    """A preallocating copy keeps size (and possibly mtime) fixed while writing; only
    ctime and allocated blocks move. That must keep the run waiting, not stop it."""
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=2)
    _write_big_gzip(fastq, n_bytes=16 * 1024 * 1024)
    fake = _FakeSleep()
    real_stat = os.stat

    def stat(p, *args, **kwargs):
        st = real_stat(p, *args, **kwargs)
        if p != fastq or fake.calls >= 3:  # copy done after the 3rd sleep
            return st
        extra = {
            name: getattr(st, name)
            for name in ("st_atime", "st_mtime", "st_ctime", "st_atime_ns", "st_mtime_ns")
        }
        extra["st_ctime_ns"] = fake.calls * 10**9  # moves with every write
        extra["st_blocks"] = int(st.st_size * (0.3 + 0.2 * fake.calls)) // 512
        extra["st_blksize"] = st.st_blksize
        return os.stat_result(list(st)[:10], extra)

    monkeypatch.setattr("agr.seq.sequencer_run.os.stat", stat)
    _install(monkeypatch, fake)
    SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)
    # 1, 2: partly allocated but ctime/blocks moving -> wait; 3: copy done, but its
    # blocks/ctime jumped since 2, so not yet settled; 4: nothing moved -> return.
    assert fake.calls == 4


def test_a_locked_unfinished_file_is_not_a_stall(tmp_path, monkeypatch):
    """A share lock means a copy is live; the run waits rather than stopping."""
    from agr.seq.sequencer_run import _unfinished

    seq_root = _make_run(tmp_path)
    locked = _fastq(seq_root, lane=1)
    real_open = open

    def open_locked(path, *args, **kwargs):
        if path == locked:
            raise PermissionError(13, "Permission denied", path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", open_locked)
    problems = _unfinished([locked])
    assert not problems[locked].stall_evidence


# --- _assess: one poll's verdict, judged across the whole run ---

from agr.seq.sequencer_run import _assess, _Stat, _Unfinished  # noqa: E402

_GB = 10**9


def _st(size=40 * _GB, mtime=1, ctime=1, written=None):
    written = size if written is None else written
    return _Stat(size, mtime, ctime, written // 512)


def _shape(path):
    return _Unfinished("%s: only 50.0%% written" % path, stall_evidence=True)


def test_assess_ready_when_settled_readable_and_finished():
    snap = {"a": _st(), "b": _st()}
    assert _assess(snap, dict(snap), [], {}, 300).state == "ready"


def test_assess_a_sequential_copier_is_progressing_not_stalled():
    """One file grows while another sits half-done and untouched, waiting its turn."""
    before = {"a": _st(ctime=1, written=10 * _GB), "b": _st(ctime=1, written=0)}
    after = {"a": _st(ctime=2, written=11 * _GB), "b": before["b"]}
    verdict = _assess(before, after, [], {"a": _shape("a"), "b": _shape("b")}, 300)
    assert verdict.state == "progressing"
    assert any(line.startswith("a: 27.5% written (+2.5% in 5 min") for line in verdict.lines)
    assert "b: only 50.0% written" in verdict.lines


def test_assess_nothing_written_and_unfinished_is_stalled():
    snap = {"a": _st(written=20 * _GB), "b": _st()}
    verdict = _assess(snap, dict(snap), [], {"a": _shape("a")}, 300)
    assert verdict == ("stalled", ["a: only 50.0% written"])


def test_assess_only_locked_and_nothing_moving_keeps_waiting():
    snap = {"a": _st()}
    verdict = _assess(snap, dict(snap), ["a: Permission denied (still locked by a copy?)"], {}, 300)
    assert verdict.state == "waiting"


def test_assess_progress_line_gives_rate_and_eta():
    before = {"a": _st(ctime=1, written=4 * _GB)}
    after = {"a": _st(ctime=2, written=5 * _GB)}  # 1 GB in 5 min = 12 GB/h, 35 GB left
    (line,) = _assess(before, after, [], {"a": _shape("a")}, 300).lines
    assert line == "a: 12.5% written (+2.5% in 5 min, ~12.0 GB/h, ~2 h 55 min left)"


def test_assess_a_growing_size_is_reported_as_a_size_change():
    before = {"a": _st(size=100)}
    after = {"a": _st(size=200, mtime=2)}
    (line,) = _assess(before, after, [], {}, 300).lines
    assert line == "a: size 100 -> 200 bytes"


def test_assess_ready_needs_nothing_at_all_to_have_moved():
    """Size and mtime settled is not enough: a write that moved only ctime/blocks
    means the copy is still live, so md5 must not run yet."""
    before = {"a": _st(ctime=1)}
    after = {"a": _st(ctime=2)}
    assert _assess(before, after, [], {}, 300).state == "progressing"


from agr.seq.sequencer_run import _should_stop  # noqa: E402


def test_should_stop_a_stall_only_once_quiet_for_stall_after_s():
    assert not _should_stop("stalled", 600, stall_after_s=900, locked_idle_after_s=3600)
    assert _should_stop("stalled", 900, stall_after_s=900, locked_idle_after_s=3600)


def test_should_stop_a_locked_wait_only_once_idle_for_locked_idle_after_s():
    assert not _should_stop("waiting", 900, stall_after_s=900, locked_idle_after_s=3600)
    assert _should_stop("waiting", 3600, stall_after_s=900, locked_idle_after_s=3600)


def test_should_never_stop_a_progressing_copy():
    assert not _should_stop("progressing", 10**9, stall_after_s=1, locked_idle_after_s=1)


def test_unfinished_does_not_count_a_recalling_file_as_stall_evidence(tmp_path, monkeypatch):
    from agr.seq.sequencer_run import _unfinished

    seq_root = _make_run(tmp_path)
    path = _fastq(seq_root, lane=1)
    _write_big_gzip(path)
    _fake_allocation(monkeypatch, path, 0.5)
    assert _unfinished([path])[path].stall_evidence
    recalling = _unfinished([path], recalled={path})[path]
    assert not recalling.stall_evidence
    assert "cold tier" in recalling.reason


# --- the loop: launch ahead of a slow copy ---


def _slow_preallocated_copy(monkeypatch, fake, path, polls):
    """Fake `os.stat` for `path`: final size from the start, mtime pinned, ctime and
    blocks advancing every poll until `polls` sleeps have passed."""
    real_stat = os.stat

    def stat(p, *args, **kwargs):
        st = real_stat(p, *args, **kwargs)
        if p != path or fake.calls >= polls:
            return st
        extra = {
            name: getattr(st, name)
            for name in ("st_atime", "st_mtime", "st_ctime", "st_atime_ns", "st_mtime_ns")
        }
        extra["st_ctime_ns"] = (fake.calls + 1) * 10**9
        extra["st_blocks"] = int(st.st_size * 0.15 * (fake.calls + 1)) // 512
        extra["st_blksize"] = st.st_blksize
        return os.stat_result(list(st)[:10], extra)

    monkeypatch.setattr("agr.seq.sequencer_run.os.stat", stat)


def test_launch_ahead_of_a_slow_copy_starts_when_it_completes(tmp_path, monkeypatch, caplog):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=2)
    _write_big_gzip(fastq, n_bytes=16 * 1024 * 1024)
    fake = _FakeSleep()
    _slow_preallocated_copy(monkeypatch, fake, fastq, polls=5)
    _install(monkeypatch, fake)
    with caplog.at_level(logging.INFO, logger="agr.seq.sequencer_run"):
        SequencerRun(seq_root, RUN).wait_until_stable(lanes=LANES, interval_s=300)
    # Polls 1-5 see blocks/ctime advance (at 5 the copy completes); at 6 nothing
    # moved and the file looks finished, so it is ready.
    assert fake.calls == 6
    assert caplog.text.count("copy in progress") == 5
    assert "% written (+15.0% in 5 min" in caplog.text and "left)" in caplog.text
    assert "copy stalled" not in caplog.text


def test_the_backstop_still_ends_a_copy_that_never_finishes(tmp_path, monkeypatch):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=2)
    _write_big_gzip(fastq, n_bytes=16 * 1024 * 1024)
    fake = _FakeSleep()
    _slow_preallocated_copy(monkeypatch, fake, fastq, polls=10**6)
    _install(monkeypatch, fake)
    with pytest.raises(SequencerRunError, match="still not stable after"):
        SequencerRun(seq_root, RUN).wait_until_stable(
            lanes=LANES, interval_s=300, max_wait_s=0
        )


def test_unfinished_reports_an_oserror_rather_than_raising(tmp_path, monkeypatch):
    from agr.seq.sequencer_run import _unfinished

    seq_root = _make_run(tmp_path)
    locked = _fastq(seq_root, lane=1)
    real_open = open

    def open_locked(path, *args, **kwargs):
        if path == locked:
            raise PermissionError(13, "Permission denied", path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", open_locked)
    problems = _unfinished([locked])
    assert list(problems) == [locked] and "Permission denied" in problems[locked].reason


# --- FileInfo md5 verification ---


def test_read_file_info_lowercases_and_handles_paired_end(tmp_path):
    path = tmp_path / "X_L01_FileInfo.txt"
    _ = path.write_text(
        "0BE20262BC4DEDDB95936E1B80780BDF  X_L01_read_1.fq.gz\n"
        "c424391eb8f5833ce68338d7e844befc  X_L01_read_2.fq.gz\n\n"
    )
    assert read_file_info(str(path)) == {
        "X_L01_read_1.fq.gz": "0be20262bc4deddb95936e1b80780bdf",
        "X_L01_read_2.fq.gz": "c424391eb8f5833ce68338d7e844befc",
    }


def test_read_file_info_rejects_a_malformed_line(tmp_path):
    path = tmp_path / "X_L01_FileInfo.txt"
    _ = path.write_text("not-an-md5\n")
    with pytest.raises(ValueError, match="line 1"):
        _ = read_file_info(str(path))


def test_verify_checksums_returns_the_verified_md5_of_every_fastq(tmp_path):
    """Returned so the demultiplexing cache key can carry the fastqs' content."""
    seq_root = _make_run(tmp_path)
    md5s = SequencerRun(seq_root, RUN).verify_checksums(lanes=LANES)
    assert md5s == {
        _fastq(seq_root, lane): hashlib.md5(open(_fastq(seq_root, lane), "rb").read()).hexdigest()
        for lane in LANES
    }


def test_verify_checksums_says_a_mismatch_may_be_a_copy_still_writing(tmp_path):
    seq_root = _make_run(tmp_path)
    _ = open(_fastq(seq_root, lane=1), "ab").write(b"y")
    with pytest.raises(SequencerRunError, match="still being written"):
        SequencerRun(seq_root, RUN).verify_checksums(lanes=LANES)


def test_verify_checksums_reports_a_mismatch_with_both_hashes(tmp_path):
    seq_root = _make_run(tmp_path)
    fastq = _fastq(seq_root, lane=3)
    _ = open(fastq, "ab").write(b"y")
    actual = hashlib.md5(open(fastq, "rb").read()).hexdigest()
    with pytest.raises(SequencerRunError, match="L03_read.fq.gz: md5 mismatch, expected [0-9a-f]{32}, got %s" % actual):
        SequencerRun(seq_root, RUN).verify_checksums(lanes=LANES)


def test_verify_checksums_requires_a_file_info(tmp_path):
    seq_root = _make_run(tmp_path)
    os.remove(os.path.join(seq_root, RUN, "L02", "%s_L02_FileInfo.txt" % RUN))
    with pytest.raises(SequencerRunError, match="L02: no .*L02_FileInfo.txt"):
        SequencerRun(seq_root, RUN).verify_checksums(lanes=LANES)


def test_verify_checksums_requires_each_fastq_to_be_listed(tmp_path):
    seq_root = _make_run(tmp_path)
    info = os.path.join(seq_root, RUN, "L04", "%s_L04_FileInfo.txt" % RUN)
    _ = open(info, "w").write("%s  someone_else.fq.gz\n" % ("0" * 32))
    with pytest.raises(SequencerRunError, match="L04: .*L04_read.fq.gz is not listed"):
        SequencerRun(seq_root, RUN).verify_checksums(lanes=LANES)


def test_verify_checksums_reports_every_problem_together(tmp_path):
    seq_root = _make_run(tmp_path)
    os.remove(os.path.join(seq_root, RUN, "L01", "%s_L01_FileInfo.txt" % RUN))
    _ = open(_fastq(seq_root, lane=4), "ab").write(b"y")
    with pytest.raises(SequencerRunError) as e:
        SequencerRun(seq_root, RUN).verify_checksums(lanes=LANES)
    assert "L01: no" in str(e.value) and "L04_read.fq.gz: md5 mismatch" in str(e.value)


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
