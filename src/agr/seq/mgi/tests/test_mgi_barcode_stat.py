"""Tests for splitBarcode's BarcodeStat.txt, against the reference run's real file.

Stdlib-only, so these run in CI.

This is the MGI analog of the five bcl-convert metrics files the Illumina report used:
MultiQC has no splitBarcode parser, so the demultiplexing stats reach the report as
custom content.
"""

import os.path

import pytest

from agr.seq.mgi.barcode_stat import (
    BarcodeStatError,
    lane_read_counts,
    parse_barcode_stat,
    write_multiqc_custom_content,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "BarcodeStat-L01.txt")


def test_parse_strips_the_barcode_prefix_from_sample_names():
    """splitBarcode prefixes every sample row with a literal "barcode"."""
    samples, totals = parse_barcode_stat(FIXTURE)

    assert [s[0] for s in samples] == ["SQ5420", "SQ5421"]
    assert samples[0] == ("SQ5420", 323321751, 13945596, 337267347, 50.617756)
    assert totals == (586028867, 26383520, 612412387, 91.912071)


def test_undecoded_is_recovered_from_the_percentage():
    """BarcodeStat.txt never states the undecoded count.

    Percentage is a share of *all* reads in the lane, decoded or not, so the lane
    total - and the undecoded remainder - follow from the Total row alone.
    """
    _, totals = parse_barcode_stat(FIXTURE)
    correct, corrected, undecoded = lane_read_counts(totals)

    assert (correct, corrected) == (586028867, 26383520)
    # 612412387 decoded is 91.912071% of the lane, so ~8.09% went undecoded.
    assert undecoded == pytest.approx(53_884_000, rel=0.001)


def test_a_total_row_that_is_not_the_sum_is_refused(tmp_path):
    """If the rows do not sum, this parser is misreading the file.

    Every downstream number would be suspect, and a half-parsed demux summary is
    worse than none.
    """
    stat = tmp_path / "BarcodeStat.txt"
    _ = stat.write_text(
        "#Barcode\t Correct\t Corrected\t Total\t Percentage(%)\n"
        "barcodeSQ5420\t 100\t 10\t 110\t 50.0\n"
        "Total\t 999\t 10\t 110\t 50.0\n"
    )
    with pytest.raises(BarcodeStatError, match="sum"):
        _ = parse_barcode_stat(str(stat))


def test_a_missing_total_row_means_the_lane_did_not_finish(tmp_path):
    stat = tmp_path / "BarcodeStat.txt"
    _ = stat.write_text(
        "#Barcode\t Correct\t Corrected\t Total\t Percentage(%)\n"
        "barcodeSQ5420\t 100\t 10\t 110\t 50.0\n"
    )
    with pytest.raises(BarcodeStatError, match="no Total row"):
        _ = parse_barcode_stat(str(stat))


def test_an_unexpected_header_is_refused(tmp_path):
    """splitBarcode changing its output must be loud, not silently mis-parsed."""
    stat = tmp_path / "BarcodeStat.txt"
    _ = stat.write_text("#Barcode\tCorrect\tSomethingNew\n" "barcodeSQ5420\t1\t2\n")
    with pytest.raises(BarcodeStatError, match="header"):
        _ = parse_barcode_stat(str(stat))


def test_writes_two_multiqc_custom_content_sections(tmp_path):
    out_dir = str(tmp_path / "multiqc_custom")
    written = write_multiqc_custom_content(
        run="DL100018469", barcode_stats={"L01": FIXTURE}, out_dir=out_dir
    )

    assert [os.path.basename(p) for p in written] == [
        "mgi_demux_lane_mqc.txt",
        "mgi_demux_sample_mqc.txt",
    ]

    lane = open(written[0]).read()
    assert "id: 'mgi_demux_lane'" in lane
    assert "plot_type: 'bargraph'" in lane
    # Explicit category order: left to itself MultiQC orders the stack by magnitude,
    # which put Undecoded *between* Correct and Corrected - the two that together
    # mean "decoded".
    assert lane.index("- Correct") < lane.index("- Corrected") < lane.index("- Undecoded")
    assert "L01\t586028867\t26383520\t" in lane


def test_per_sample_section_is_a_table_not_a_bargraph(tmp_path):
    """A GBS lane holds ~3800 samples.

    The question asked of per-sample counts is "which samples dropped out", which is
    a sort rather than a shape; and above 500 rows MultiQC switches a table to a
    violin plot itself, which stays readable at that size.
    """
    out_dir = str(tmp_path / "multiqc_custom")
    _, sample_file = write_multiqc_custom_content(
        run="DL100018469", barcode_stats={"L01": FIXTURE}, out_dir=out_dir
    )

    content = open(sample_file).read()
    assert "plot_type: 'table'" in content
    # Namespaced with run and lane, so the row carries the same context as the
    # sample's FastQC entry without being merged into it.
    assert "DL100018469_L01_SQ5420\tL01\t" in content


def test_lanes_are_emitted_in_order(tmp_path):
    out_dir = str(tmp_path / "multiqc_custom")
    lane_file, _ = write_multiqc_custom_content(
        run="DL100018469",
        barcode_stats={"L02": FIXTURE, "L01": FIXTURE},
        out_dir=out_dir,
    )
    content = open(lane_file).read()
    assert content.index("L01\t") < content.index("L02\t")
