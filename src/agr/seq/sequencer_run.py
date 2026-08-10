import logging
import os
import os.path

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

    def lane_fastq(self, lane: int) -> str:
        """The lane's single undemultiplexed fastq, as the sequencer writes it."""
        return os.path.join(
            self.lane_dir(lane), "%s_L%02d_read.fq.gz" % (self._run_name, lane)
        )

    def validate(self, lanes: list[int]):
        """Check the run looks complete enough to process.

        **This does not wait.** The run is required to have finished before the
        pipeline is launched, which the operator confirms; this only fails fast and
        legibly on a typo'd run name or a half-copied run, rather than surfacing
        later as a confusing error from deep inside splitBarcode.

        `lanes` comes from the sample sheet: nothing in the run directory says how
        many lanes to expect.

        MGI has no `RunInfo.xml`, so what is checked is one `L0n` directory per lane
        with its undemultiplexed fastq present. Note the instrument also writes
        `<seq_root>/Info/Upload/<run>_L0<n>_Success.txt`, but those attest to
        instrument *upload* rather than to the fastqs landing on eRI - in the
        reference run they carry 24 Jul mtimes while the lane directories are dated
        28-29 Jul - so they are not what is checked here.
        """
        if missing := [
            "L%02d: no %s" % (lane, self.lane_fastq(lane))
            for lane in lanes
            if not os.path.exists(self.lane_fastq(lane))
        ]:
            raise SequencerRunError(
                "run %s is not ready to process:\n  %s"
                % (self._run_name, "\n  ".join(missing))
            )
        logger.info("run %s has all %d lanes", self._run_name, len(lanes))

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
