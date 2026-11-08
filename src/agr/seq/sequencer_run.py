import hashlib
import logging
import os
import os.path
import time
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

from agr.seq.mgi.barcodes import (
    BarcodeLayoutError,
    BioInfoError,
    bioinfo_path,
    read_bioinfo,
    read_files,
)
from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


class SequencerRunError(Exception):
    def __init__(self, msg: str, e: Exception | None = None):
        super().__init__("%s: %s" % (msg, e) if e is not None else msg)
        self._msg = msg
        self._e = e


def find_seq_root(seq_roots: list[str], run_name: str) -> str:
    """The instrument directory in `seq_roots` that holds `run_name`.

    Only an exact `<root>/<run_name>` directory counts, so suffixed copies such as
    `<run>_corrupt` never match. A run reached from several roots through symlinks is
    one run, and the **first** root in list order wins: keeping already-processed runs
    on the root they were processed under keeps their redun cache (the root ends up in
    the splitBarcode arguments). Distinct copies in different roots are refused rather
    than guessed between.
    """
    found = [
        root for root in seq_roots if os.path.isdir(os.path.join(root, run_name))
    ]
    if not found:
        raise SequencerRunError(
            "run %s not found in any of %s" % (run_name, ", ".join(seq_roots))
        )
    first = os.path.join(found[0], run_name)
    distinct = [
        root
        for root in found[1:]
        if not os.path.samefile(first, os.path.join(root, run_name))
    ]
    if distinct:
        raise SequencerRunError(
            "ambiguous: run %s found as distinct directories in %s; remove or rename "
            "all but one" % (run_name, ", ".join([found[0]] + distinct))
        )
    return found[0]


class SequencerRun:
    """An MGI (DNBSEQ) sequencing run.

    `seq_root` is the **instrument** directory, not the run-data root, so the plain
    `join(seq_root, run_name)` below works and the completion sentinels are a sibling
    of the run directory. Runs have been synced to more than one instrument directory
    over time, so the context lists several and `find_seq_root` picks the one holding
    the run; this class still takes exactly one.

    Note there is no `sample_sheet_path`: an MGI sheet lives outside the run tree
    entirely, at `<sample_sheet_root>/<flowcell>.csv`, and is supplied separately.
    """

    def __init__(self, seq_root: str, run_name: str):
        self._seq_root = seq_root
        self._run_name = run_name
        self._dir = os.path.join(seq_root, run_name)
        if not os.path.isdir(self._dir):
            raise SequencerRunError("no such directory %s" % self._dir)

    @property
    def seq_root(self) -> str:
        return self._seq_root

    @property
    def dir(self) -> str:
        return self._dir

    @property
    def name(self) -> str:
        """For MGI the run name is also the flowcell id, e.g. DL100018469."""
        return self._run_name

    def lane_dir(self, lane: int) -> str:
        return os.path.join(self._dir, "L%02d" % lane)

    def lane_fastqs(self, lane: int) -> list[str]:
        """The lane's undemultiplexed fastq(s), as the sequencer writes them.

        Resolved by `read_files`, the same lookup `lane_plan` uses, so the two can
        never disagree about which files make up a lane. That lookup also finds a
        paired-end `_read_1`/`_read_2` pair, which `validate` rejects.
        """
        return read_files(self._dir, self._run_name, lane).paths

    def validate(self, lanes: list[int]):
        """Check the run looks complete enough to process.

        **This does not wait** - that is `wait_until_stable`. This fails fast and
        legibly, before any wait, on everything that can be known at launch: a
        typo'd run name, a lane whose fastqs have not appeared at all, a paired-end
        run, and a lane whose `BioInfo.csv` or `FileInfo.txt` is missing, unreadable
        or disagrees with its fastqs. Those small files land before the fastq (the
        copier writes a lane's small files first), so even a run launched ahead of its
        copy has them; otherwise a launch-ahead would find out only after a wait of
        up to 24 h.

        gbs_prism processes **single-end runs only**. The MGI demultiplexing code
        (`agr.seq.mgi.barcodes`) can lay out a paired-end lane, but nothing
        downstream of it handles paired reads, so a paired-end run is refused here
        before any Slurm job is submitted.

        `lanes` comes from the sample sheet: nothing in the run directory says how
        many lanes to expect.

        MGI has no `RunInfo.xml`, so what is checked is one `L0n` directory per lane
        with its undemultiplexed fastq(s) present. Note the instrument also writes
        `<seq_root>/Info/Upload/<run>_L0<n>_Success.txt`, but those attest to
        instrument *upload* rather than to the fastqs landing on eRI - in the
        reference run they carry 24 Jul mtimes while the lane directories are dated
        28-29 Jul - so they are not what is checked here.

        All problems are collected and raised together as one `SequencerRunError`.
        """
        problems = []
        fastqs: dict[int, list[str]] = {}
        for lane in lanes:
            try:
                reads = read_files(self._dir, self._run_name, lane)
            except BarcodeLayoutError as e:
                problems.append("L%02d: %s" % (lane, e))
                continue
            if reads.is_pe:
                problems.append(
                    "L%02d: run is paired-end (%s, %s); gbs_prism processes "
                    "single-end runs only"
                    % (
                        lane,
                        os.path.basename(reads.r1),
                        os.path.basename(reads.r2 or ""),
                    )
                )
            fastqs[lane] = reads.paths
            try:
                bio = read_bioinfo(bioinfo_path(self._dir, lane))
            except (BioInfoError, OSError) as e:
                problems.append("L%02d: %s" % (lane, e))
                continue
            if bio.is_pe != reads.is_pe:
                problems.append(
                    "L%02d: %s declares %s but the run directory holds %s"
                    % (
                        lane,
                        bio.path,
                        "paired-end" if bio.is_pe else "single-end",
                        "a paired-end pair of fastqs" if reads.is_pe else "a single fastq",
                    )
                )
        problems += self._expected_md5s(fastqs)[1]
        if problems:
            raise SequencerRunError(
                "run %s is not ready to process:\n  %s"
                % (self._run_name, "\n  ".join(problems))
            )
        logger.info("run %s has all %d lanes", self._run_name, len(lanes))

    def wait_until_stable(
        self,
        lanes: list[int],
        interval_s: float = 300,
        max_wait_s: float = 24 * 3600,
        stall_after_s: float = 15 * 60,
        locked_idle_after_s: float = 60 * 60,
    ):
        """Wait until every lane fastq is a complete, settled copy; meanwhile wait as
        long as the copy is progressing, and stop once it has clearly stalled.

        Fastqs reach eRI by an SMB copy that can still be running when the pipeline
        is launched - deliberately so, as a run may be launched ahead of a slow copy.
        Polls every `interval_s`, so this always takes at least one interval: two
        snapshots apart in time are the only evidence of stability. At each poll:

        - **Ready**: nothing about any file changed - size, mtime, ctime, allocated
          blocks - it opens (a copy's share lock surfaces as EACCES), and it looks
          like a finished gzip copy (`_unfinished`). Returns.
        - **Progressing**: *any* fastq was written to since the last poll. Keeps
          waiting, logging % written and an ETA, and resets the idle clock. Judged
          across the run, not per file: a copier doing one file at a time leaves later
          files half-done and untouched meanwhile. ctime and blocks matter because a
          preallocating copy has its final size from the start.
        - **Stalled**: nothing in the run was written to, yet a readable file is
          unfinished. Raises once nothing has been written for `stall_after_s`
          (15 min) - not after one quiet interval, which a transient SMB pause can
          produce.
        - **Waiting**: nothing moving, and what is not ready is only locked (or still
          being recalled from the cold tier). A lock means a live copy, but not
          forever: raises once nothing has been written for `locked_idle_after_s`
          (1 h), as a hung copier.

        Raises after `max_wait_s` (24 h) whatever the state, as a backstop.

        Readable files are probed even while others are locked, so one lane's lock
        cannot hide another lane's stalled copy. A file seen on the cold tier at any
        poll is being recalled, so its allocation shortfall is never stall evidence.

        On tiered storage the open probe recalls each migrated file before returning,
        which can block well beyond `interval_s`; that recall is needed by
        `lane_plan` anyway, so it is logged rather than avoided.
        """
        paths = [path for lane in lanes for path in self.lane_fastqs(lane)]
        start = time.monotonic()
        previous, previous_t = _snapshot(paths), start
        idle_since: float | None = None
        recalled: set[str] = set()
        while True:
            time.sleep(interval_s)
            now = time.monotonic()
            current = _snapshot(paths)
            unreadable: dict[str, str] = {}
            unfinished: dict[str, _Unfinished] = {}
            if all(current[p] == previous[p] for p in paths):
                logger.info(
                    "run %s: fastqs unchanged over %ds, checking all %d can be opened",
                    self._run_name,
                    interval_s,
                    len(paths),
                )
                if stubs := _cold_stubs(paths):
                    recalled.update(stubs)
                    logger.info(
                        "run %s: %d fastq(s) are on the cold tier (offline); opening "
                        "them recalls the whole file, which may take a while:\n  %s",
                        self._run_name,
                        len(stubs),
                        "\n  ".join(stubs),
                    )
                unreadable = _unreadable(paths)
                unfinished = _unfinished(
                    [p for p in paths if p not in unreadable], recalled=recalled
                )

            verdict = _assess(
                previous, current, list(unreadable.values()), unfinished, interval_s
            )
            if verdict.state == _READY:
                logger.info(
                    "run %s: all %d fastqs complete and stable over %ds",
                    self._run_name,
                    len(paths),
                    interval_s,
                )
                return

            if verdict.state == _PROGRESSING:
                idle_since = None
            elif idle_since is None:
                idle_since = previous_t
            idle_s = 0.0 if idle_since is None else now - idle_since
            idle_min = int(idle_s // 60)

            if _should_stop(verdict.state, idle_s, stall_after_s, locked_idle_after_s):
                if verdict.state == _STALLED:
                    raise SequencerRunError(
                        "run %s: copy stalled, nothing written to these fastqs in the "
                        "last %d min:\n  %s\nRe-copy them and relaunch."
                        % (self._run_name, idle_min, "\n  ".join(verdict.lines))
                    )
                raise SequencerRunError(
                    "run %s: fastqs locked or still recalling, but nothing written for "
                    "%d min - the copy may be hung:\n  %s\nCheck the copier, then "
                    "relaunch." % (self._run_name, idle_min, "\n  ".join(verdict.lines))
                )
            elapsed = now - start
            if elapsed >= max_wait_s:
                raise SequencerRunError(
                    "run %s fastqs still not stable after %d min:\n  %s"
                    % (self._run_name, elapsed // 60, "\n  ".join(verdict.lines))
                )
            if verdict.state == _PROGRESSING:
                status = "copy in progress"
            elif verdict.state == _STALLED:
                status = "no progress for %d min (stopping at %d min if nothing is written)" % (
                    idle_min,
                    stall_after_s // 60,
                )
            else:
                status = "waiting for fastqs to settle, no change for %d min" % idle_min
            logger.info(
                "run %s: %s:\n  %s", self._run_name, status, "\n  ".join(verdict.lines)
            )
            previous, previous_t = current, now

    def file_info_path(self, lane: int) -> str:
        """The instrument's per-lane md5 manifest, `L0n/<run>_L0n_FileInfo.txt`."""
        return os.path.join(
            self.lane_dir(lane), "%s_L%02d_FileInfo.txt" % (self._run_name, lane)
        )

    def _expected_md5s(
        self, fastqs: dict[int, list[str]]
    ) -> tuple[dict[str, str], list[str]]:
        """Each lane fastq's md5 according to its lane's `FileInfo.txt`, and the
        problems that leave a fastq without one: a missing or malformed FileInfo, or
        a fastq it does not list. Without an expected hash there is nothing to vouch
        for the file, so each of those is an error.
        """
        problems = []
        expected: dict[str, str] = {}
        for lane, paths in fastqs.items():
            info_path = self.file_info_path(lane)
            try:
                info = read_file_info(info_path)
            except FileNotFoundError:
                problems.append("L%02d: no %s" % (lane, info_path))
                continue
            except (ValueError, OSError) as e:
                problems.append("L%02d: %s" % (lane, e))
                continue
            for path in paths:
                name = os.path.basename(path)
                if name in info:
                    expected[path] = info[name]
                else:
                    problems.append(
                        "L%02d: %s is not listed in %s" % (lane, name, info_path)
                    )
        return expected, problems

    def verify_checksums(self, lanes: list[int], max_workers: int = 8) -> dict[str, str]:
        """Check every lane fastq's md5 against the instrument's `FileInfo.txt`, and
        return the verified md5 per fastq path.

        This is the definitive check that the fastqs on eRI are the ones the
        instrument wrote: a copy can stall or be rewritten while still looking
        complete (see `wait_until_stable`). Files are hashed in parallel, about 85 s
        per 40 GB lane on login-1 (about 1.5 min for 4 lanes).

        The md5s are returned so that demultiplexing can be keyed on the fastqs'
        verified content rather than on their paths alone.

        `validate` has already checked each FileInfo is present and lists its fastq;
        the same problems are still reported here, so this stands alone. All problems
        are collected and raised together as one `SequencerRunError`.
        """
        expected, problems = self._expected_md5s(
            {lane: self.lane_fastqs(lane) for lane in lanes}
        )

        start = time.monotonic()
        mismatched = False
        if expected:
            logger.info(
                "run %s: verifying md5 of %d fastq(s) against FileInfo",
                self._run_name,
                len(expected),
            )
            with ThreadPoolExecutor(max_workers=min(max_workers, len(expected))) as pool:
                actual = dict(zip(expected, pool.map(_md5, expected)))
            for path, want in expected.items():
                if actual[path] != want:
                    mismatched = True
                    problems.append(
                        "%s: md5 mismatch, expected %s, got %s" % (path, want, actual[path])
                    )

        if problems:
            raise SequencerRunError(
                "run %s fastqs failed integrity checks:\n  %s%s"
                % (
                    self._run_name,
                    "\n  ".join(problems),
                    "\nAn md5 mismatch means the copy is corrupt or was still being "
                    "written: let the copy finish, or re-copy, then relaunch."
                    if mismatched
                    else "",
                )
            )
        logger.info(
            "run %s: md5 of all %d fastq(s) match FileInfo (%ds)",
            self._run_name,
            len(expected),
            time.monotonic() - start,
        )
        return expected

    # TODO move this to a more appropriate class, perhaps
    def exists_in_database(self) -> bool:
        """Use GQuery to determine whether the run exists in the database.

        `platform=mgi` is required: gquery's `factory.for_platform` defaults to
        `illumina`, and `lab_report` is run-scoped, so without it this looks the run
        up as an Illumina run and never finds it.
        """
        # TODO: there ought to be a nicer way to do this than failure code from gquery subprocess
        with open("/dev/null", "wb") as devnull_f:
            gquery = run_catching_stderr(
                [
                    "gquery",
                    "-t",
                    "lab_report",
                    "-p",
                    "name=illumina_run_details;platform=mgi",
                    self._run_name,
                ],
                stdout=devnull_f,
                stderr=devnull_f,
            )
            return gquery.returncode == 0


class _Stat(NamedTuple):
    size: int
    mtime_ns: int
    # Every write moves these, even when a preallocated size and an unflushed mtime
    # do not; they tell a live copy from a stalled one.
    ctime_ns: int
    blocks: int


FileStat = _Stat | None


def _snapshot(paths: list[str]) -> dict[str, FileStat]:
    """A `_Stat` per path, or None if it cannot be stat'd (e.g. mid-rename)."""
    snapshot: dict[str, FileStat] = {}
    for path in paths:
        try:
            st = os.stat(path)
            snapshot[path] = _Stat(
                st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_blocks
            )
        except OSError:
            snapshot[path] = None
    return snapshot


def _describe_change(before: FileStat, after: FileStat) -> str:
    if after is None:
        return "missing"
    if before is None or before.size != after.size:
        was = "?" if before is None else before.size
        return "size %s -> %d bytes" % (was, after.size)
    return "modified, size unchanged at %d bytes" % after.size


_READY, _PROGRESSING, _WAITING, _STALLED = "ready", "progressing", "waiting", "stalled"


class _Verdict(NamedTuple):
    state: str
    lines: list[str]


def _assess(
    previous: dict[str, FileStat],
    current: dict[str, FileStat],
    unreadable: list[str],
    unfinished: dict[str, "_Unfinished"],
    interval_s: float,
) -> _Verdict:
    """Decide one poll of `wait_until_stable`; pure, so the rules are testable alone.

    `unreadable` and `unfinished` are the probe results, empty when the probes did
    not run (because something about some file had changed). Ready needs nothing at
    all to have changed: a write that moved only ctime or blocks is a live copy, and
    md5ing it would fail with the wrong advice. That costs at most one extra interval
    after a chmod or a recall triggered by an earlier poll's probe.

    The verdict does not decide when to *stop*: see `_should_stop`.
    """
    progressed = [p for p in current if current[p] != previous[p]]
    if not progressed and not unreadable and not unfinished:
        return _Verdict(_READY, [])

    if progressed:
        lines = [_progress_line(p, previous[p], current[p], interval_s) for p in progressed]
        lines += [u.reason for p, u in unfinished.items() if p not in progressed]
        return _Verdict(_PROGRESSING, lines)

    stalled = [u.reason for u in unfinished.values() if u.stall_evidence]
    if stalled:
        return _Verdict(_STALLED, stalled)
    return _Verdict(_WAITING, unreadable + [u.reason for u in unfinished.values()])


def _should_stop(
    state: str, idle_s: float, stall_after_s: float, locked_idle_after_s: float
) -> bool:
    """Whether a poll's verdict, after `idle_s` with nothing written anywhere in the
    run, ends the wait: a stall after `stall_after_s`, a locked (or recalling) wait
    after the longer `locked_idle_after_s`. A progressing copy never stops here; only
    the backstop ends it.
    """
    if state == _STALLED:
        return idle_s >= stall_after_s
    if state == _WAITING:
        return idle_s >= locked_idle_after_s
    return False


def _progress_line(path: str, before: FileStat, after: FileStat, interval_s: float) -> str:
    """One file's copy progress since the last poll, with an ETA when it can tell."""
    if after is None or before is None or before.size != after.size:
        return "%s: %s" % (path, _describe_change(before, after))
    if after.size == 0:
        return "%s: modified, empty" % path
    written = min(after.blocks * 512, after.size)
    pct = 100 * written / after.size
    delta = (after.blocks - before.blocks) * 512
    remaining = after.size - written
    if delta <= 0 or remaining <= 0:
        return "%s: %.1f%% written, modified" % (path, pct)
    rate = delta / interval_s  # bytes/s
    return "%s: %.1f%% written (+%.1f%% in %d min, ~%.1f GB/h, ~%s left)" % (
        path,
        pct,
        100 * delta / after.size,
        interval_s // 60,
        rate * 3600 / 1e9,
        _duration(remaining / rate),
    )


def _duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 60:
        return "%d min" % minutes
    return "%d h %d min" % (minutes // 60, minutes % 60)


# A migrated (cold-tier, OFFLINE) GPFS file keeps its size but has no blocks; a copy
# that stalled part-way has *most* of its blocks (99% for DL100022099 L02 on 6 Nov,
# 68-72% for DL100018239_corrupt). Below this fraction a file is on the cold tier.
_COLD_ALLOCATED_FRACTION = 0.01

# Allocation can trail size by up to a block on a healthy file; a stalled copy's
# unwritten tail is far larger (185-384 MiB seen).
_UNALLOCATED_SLACK = 1024 * 1024

# Compressed data never contains this much zero run; an unwritten tail does.
_TAIL_PROBE = 64 * 1024

_GZIP_MAGIC = b"\x1f\x8b"


def _allocated(st: os.stat_result) -> int:
    return st.st_blocks * 512


def _cold_stubs(paths: list[str]) -> list[str]:
    """The paths migrated to the cold tier: (almost) no blocks allocated.

    A *partly* allocated file is not cold - it is an incomplete copy, which
    `_unfinished` reports.
    """
    stubs = []
    for path in paths:
        try:
            st = os.stat(path)
        except OSError:
            continue
        if st.st_size > 0 and _allocated(st) < st.st_size * _COLD_ALLOCATED_FRACTION:
            stubs.append(path)
    return stubs


class _Unfinished(NamedTuple):
    reason: str
    # False when the file could not even be read (e.g. a copy's share lock): that is
    # evidence of a live copy, never of a stalled one.
    stall_evidence: bool


def _unfinished(
    paths: list[str], recalled: set[str] | frozenset[str] = frozenset()
) -> dict[str, _Unfinished]:
    """The paths which do not look like a finished gzip copy, with why.

    Run only on files that open, i.e. after the open probe has started any cold-tier
    recall, and never on locked files: the allocation test below needs no open, so it
    would read a live locked copy as stall evidence.

    A file in `recalled` was seen offline during this wait. If the recall has not
    finished (recall need not block until the whole file is resident), it is partly
    allocated like a stalled copy, but that is no evidence of one. The content
    checks still apply to it: what a read returns is the real data.
    """
    unfinished: dict[str, _Unfinished] = {}

    def shape(path: str, reason: str):
        unfinished[path] = _Unfinished("%s: %s" % (path, reason), stall_evidence=True)

    for path in paths:
        try:
            st = os.stat(path)
            unallocated = st.st_size - _allocated(st)
            if unallocated > _UNALLOCATED_SLACK and path in recalled:
                unfinished[path] = _Unfinished(
                    "%s: %.1f%% recalled from the cold tier so far, recall still in "
                    "progress?" % (path, 100 * _allocated(st) / st.st_size),
                    stall_evidence=False,
                )
                continue
            if unallocated > _UNALLOCATED_SLACK:
                shape(
                    path,
                    "only %.1f%% written (%d MiB unallocated), copy unfinished?"
                    % (
                        100 * _allocated(st) / st.st_size,
                        unallocated // (1024 * 1024),
                    ),
                )
                continue
            with open(path, "rb") as f:
                head = f.read(len(_GZIP_MAGIC))
                _ = f.seek(max(0, st.st_size - _TAIL_PROBE))
                tail = f.read(_TAIL_PROBE)
        except OSError as e:
            unfinished[path] = _Unfinished("%s: %s" % (path, e), stall_evidence=False)
            continue
        if head != _GZIP_MAGIC:
            shape(
                path,
                "not gzip at start (%s), copy unfinished or corrupt?"
                % (head.hex(" ") or "empty"),
            )
        elif not tail.strip(b"\0"):
            shape(path, "last %d KiB are all zero, copy unfinished?" % (len(tail) // 1024))
    return unfinished


def read_file_info(path: str) -> dict[str, str]:
    """Parse an MGI `FileInfo.txt`: `<MD5>  <file name>` per line -> {name: md5}.

    MD5s are lowercased to compare with `hashlib`. Raises `ValueError` on a line
    that is not an md5 and a name.
    """
    info = {}
    with open(path) as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) != 2 or len(fields[0]) != 32:
                raise ValueError("%s line %d: expected '<md5>  <name>': %r" % (path, n, line))
            info[fields[1]] = fields[0].lower()
    return info


def _md5(path: str, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def _unreadable(paths: list[str]) -> dict[str, str]:
    """The paths which cannot be opened, with why - typically a copy's share lock."""
    unreadable = {}
    for path in paths:
        try:
            with open(path, "rb") as f:
                _ = f.read(1)
        except OSError as e:
            unreadable[path] = "%s: %s (still locked by a copy?)" % (path, e)
    return unreadable
