"""Tests for the lane-merge policy.

Stdlib-only, so these run in CI.

The policy exists because two situations look identical on disk - a lane whose
demultiplexing failed, and a lane where the library legitimately underperformed - and
they want opposite handling. Read counts from `BarcodeStat.txt` are what tells them
apart.
"""

import pytest

from agr.gbs_prism.merge_policy import (
    MIN_LIBRARY_READS,
    MergePolicyError,
    lanes_to_merge,
)

L1, L2 = 1, 2
PLENTY = 200_000_000  # what a real GBS library yields in one lane


def test_merges_every_lane_in_order():
    paths = lanes_to_merge(
        library="SQ5420",
        expected_lanes=[L1, L2],
        found={L2: "/x/L02.fq.gz", L1: "/x/L01.fq.gz"},
        read_counts={L1: PLENTY, L2: PLENTY},
    )
    # Lane order, not dict order - the merged file should be reproducible.
    assert paths == ["/x/L01.fq.gz", "/x/L02.fq.gz"]


def test_a_library_that_clears_the_bar_on_one_lane_is_merged():
    """The "legitimately underperformed in one lane" case.

    A lane can yield almost nothing for a library for ordinary wet-lab reasons. That
    is not a reason to throw away a library which is otherwise perfectly usable.
    """
    paths = lanes_to_merge(
        library="SQ5420",
        expected_lanes=[L1, L2],
        found={L1: "/x/L01.fq.gz"},
        read_counts={L1: PLENTY, L2: 0},
    )
    assert paths == ["/x/L01.fq.gz"]


def test_a_library_below_the_threshold_is_refused():
    """The "demultiplexing failed" case.

    Merging anyway would hand KGD a library that looks whole but is not, and nothing
    downstream would notice.
    """
    with pytest.raises(MergePolicyError, match="SQ5420"):
        _ = lanes_to_merge(
            library="SQ5420",
            expected_lanes=[L1, L2],
            found={L1: "/x/L01.fq.gz"},
            read_counts={L1: 5_000, L2: 0},
        )


def test_the_threshold_is_on_the_library_total_not_per_lane():
    """Lanes are merged, so what matters is the depth of the merged result."""
    half = MIN_LIBRARY_READS // 2
    paths = lanes_to_merge(
        library="SQ5420",
        expected_lanes=[L1, L2],
        found={L1: "/x/L01.fq.gz", L2: "/x/L02.fq.gz"},
        read_counts={L1: half + 1, L2: half + 1},
    )
    assert len(paths) == 2


def test_a_library_with_no_output_at_all_is_refused():
    with pytest.raises(MergePolicyError, match="no fastq"):
        _ = lanes_to_merge(
            library="SQ5420",
            expected_lanes=[L1, L2],
            found={},
            read_counts={L1: 0, L2: 0},
        )


def test_the_error_reports_the_counts_it_decided_on():
    """A refusal has to say why, or the operator cannot tell demux failure from yield."""
    with pytest.raises(MergePolicyError) as excinfo:
        _ = lanes_to_merge(
            library="SQ5420",
            expected_lanes=[L1, L2],
            found={L1: "/x/L01.fq.gz"},
            read_counts={L1: 5_000, L2: 0},
        )
    message = str(excinfo.value)
    assert "5,000" in message or "5000" in message
    assert "L01" in message and "L02" in message


def test_missing_read_counts_are_treated_as_zero_not_as_an_error():
    """A lane that produced nothing has no BarcodeStat row for the library."""
    paths = lanes_to_merge(
        library="SQ5420",
        expected_lanes=[L1, L2],
        found={L1: "/x/L01.fq.gz"},
        read_counts={L1: PLENTY},
    )
    assert paths == ["/x/L01.fq.gz"]
