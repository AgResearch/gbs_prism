import logging
import os
import os.path
import time

from agr.seq.mgi.barcodes import BarcodeLayoutError, read_files
from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


class SequencerRunError(Exception):
    def __init__(self, msg: str, e: Exception | None = None):
        super().__init__("%s: %s" % (msg, e) if e is not None else msg)
        self._msg = msg
        self._e = e


class SequencerRun:
    """An MGI (DNBSEQ) sequencing run.

    `seq_root` is the **instrument** directory, not the run-data root: MGI nests runs
    three levels below run_data (`<run_data>/T1+/INV-MGI-T1/<flowcell>`) where
    Illumina runs sat flat. Pointing seq_root at the instrument keeps the plain
    `join(seq_root, run_name)` below working, and puts the completion sentinels a
    sibling of the run directory. That is a context-file change rather than a code
    change, which is why it is preferred to teaching this class to search.

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

        **This does not wait** - that is `wait_until_stable`. This only fails fast and
        legibly on a typo'd run name, a lane whose fastqs have not appeared at all, or
        a paired-end run, rather than surfacing later as a confusing error from deep
        inside splitBarcode or the downstream GBS analysis.

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
        """
        problems = []
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
        if problems:
            raise SequencerRunError(
                "run %s is not ready to process:\n  %s"
                % (self._run_name, "\n  ".join(problems))
            )
        logger.info("run %s has all %d lanes", self._run_name, len(lanes))

    def wait_until_stable(
        self, lanes: list[int], interval_s: float = 300, max_wait_s: float = 7200
    ):
        """Wait until every lane fastq has stopped changing and can be opened.

        Fastqs reach eRI by an SMB copy that can still be running when the pipeline
        is launched. A file being copied may already have its full size (Windows
        copies preallocate), and the copy's share-mode lock surfaces on GPFS as
        EACCES on open. So a file is stable only when its size *and* mtime are
        unchanged across a whole `interval_s`, and it opens for reading.

        Polls every `interval_s`, so this always takes at least one interval: two
        snapshots apart in time are the only evidence of stability. Raises
        `SequencerRunError` naming the unsettled files after `max_wait_s`.

        On tiered storage the open probe recalls each migrated file in full before
        returning, which can block well beyond `max_wait_s`; that recall is needed by
        `lane_plan` anyway, so it is logged rather than avoided.
        """
        paths = [path for lane in lanes for path in self.lane_fastqs(lane)]
        start = time.monotonic()
        previous = _snapshot(paths)
        while True:
            time.sleep(interval_s)
            current = _snapshot(paths)
            not_ready = [
                "%s: %s" % (path, _describe_change(previous[path], stat))
                for path, stat in current.items()
                if stat is None or stat != previous[path]
            ]
            if not not_ready:
                logger.info(
                    "run %s: fastqs unchanged over %ds, checking all %d can be opened",
                    self._run_name,
                    interval_s,
                    len(paths),
                )
                if stubs := _tiered_stubs(paths):
                    logger.info(
                        "run %s: %d fastq(s) are on tiered storage; opening them "
                        "recalls the whole file, which may take a while:\n  %s",
                        self._run_name,
                        len(stubs),
                        "\n  ".join(stubs),
                    )
                not_ready = _unreadable(paths)
            if not not_ready:
                logger.info(
                    "run %s: all %d fastqs stable over %ds",
                    self._run_name,
                    len(paths),
                    interval_s,
                )
                return
            elapsed = time.monotonic() - start
            if elapsed >= max_wait_s:
                raise SequencerRunError(
                    "run %s fastqs still not stable after %d min:\n  %s"
                    % (self._run_name, elapsed // 60, "\n  ".join(not_ready))
                )
            logger.info(
                "run %s: waiting for fastqs to settle:\n  %s",
                self._run_name,
                "\n  ".join(not_ready),
            )
            previous = current

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


FileStat = tuple[int, int] | None


def _snapshot(paths: list[str]) -> dict[str, FileStat]:
    """`(size, mtime_ns)` per path, or None if it cannot be stat'd (e.g. mid-rename)."""
    snapshot: dict[str, FileStat] = {}
    for path in paths:
        try:
            st = os.stat(path)
            snapshot[path] = (st.st_size, st.st_mtime_ns)
        except OSError:
            snapshot[path] = None
    return snapshot


def _describe_change(before: FileStat, after: FileStat) -> str:
    if after is None:
        return "missing"
    if before is None or before[0] != after[0]:
        was = "?" if before is None else before[0]
        return "size %s -> %d bytes" % (was, after[0])
    return "modified, size unchanged at %d bytes" % after[0]


def _tiered_stubs(paths: list[str]) -> list[str]:
    """The paths not fully resident on disk: migrated to a cold tier, or mid-recall.

    A migrated GPFS file keeps its size but has (almost) no blocks allocated.
    """
    stubs = []
    for path in paths:
        try:
            st = os.stat(path)
        except OSError:
            continue
        if st.st_size > 0 and st.st_blocks * 512 < st.st_size:
            stubs.append(path)
    return stubs


def _unreadable(paths: list[str]) -> list[str]:
    """The paths which cannot be opened, with why - typically a copy's share lock."""
    unreadable = []
    for path in paths:
        try:
            with open(path, "rb") as f:
                _ = f.read(1)
        except OSError as e:
            unreadable.append("%s: %s (still locked by a copy?)" % (path, e))
    return unreadable
