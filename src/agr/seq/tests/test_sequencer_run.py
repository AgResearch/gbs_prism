"""Tests for the MGI run directory.

Stdlib-only, so these run in CI.

There is deliberately no waiting here: the run is required to have finished before
the pipeline is launched, which the operator confirms. `validate` only fails fast on
a run that is obviously not ready.
"""

import pytest

from agr.seq.sequencer_run import SequencerRun, SequencerRunError

RUN = "DL100018469"
LANES = [1, 2, 3, 4]


def _make_run(tmp_path, lanes=LANES, fastq_lanes=None):
    """Build an MGI run tree: <seq_root>/<run>/L0n."""
    seq_root = tmp_path / "INV-MGI-T1"
    run_dir = seq_root / RUN
    fastq_lanes = lanes if fastq_lanes is None else fastq_lanes

    for lane in lanes:
        (run_dir / ("L%02d" % lane)).mkdir(parents=True)
    for lane in fastq_lanes:
        _ = (
            run_dir / ("L%02d" % lane) / ("%s_L%02d_read.fq.gz" % (RUN, lane))
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
    assert run.lane_fastq(1).endswith("L01/%s_L01_read.fq.gz" % RUN)


def test_validate_accepts_a_complete_run(tmp_path):
    seq_root = _make_run(tmp_path)
    SequencerRun(seq_root, RUN).validate(lanes=LANES)  # must not raise


def test_validate_names_the_lanes_that_are_not_ready(tmp_path):
    """Fails fast and legibly rather than surfacing from deep inside splitBarcode."""
    seq_root = _make_run(tmp_path, fastq_lanes=[1, 2])
    run = SequencerRun(seq_root, RUN)
    with pytest.raises(SequencerRunError, match="L03"):
        run.validate(lanes=LANES)


def test_missing_run_directory_is_an_error(tmp_path):
    with pytest.raises(SequencerRunError):
        _ = SequencerRun(str(tmp_path), "NO_SUCH_RUN")
