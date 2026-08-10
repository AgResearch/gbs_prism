"""Tests for MGI sample sheet parsing, against the real DL100018469 sheet.

Stdlib-only by design, so these run under `nix run '.#tests'` as well as in the
devshell - see CLAUDE.md on why CI can collect nothing that imports gquery or redun.
"""

import os.path

import pytest

from agr.seq.mgi.sample_sheet import (
    MgiSampleSheetError,
    gbs_library_specs,
    lane_label,
    lanes_by_library,
    lanes_in_sample_sheet,
    parse_lanes,
    read_sample_sheet,
    samples_for_lane,
)

REFERENCE_SHEET = os.path.join(os.path.dirname(__file__), "DL100018469.csv")


@pytest.fixture
def sheet():
    return read_sample_sheet(REFERENCE_SHEET)


def test_header_is_read_as_key_value_pairs(sheet):
    assert sheet.header["Flowcell"] == "DL100018469"
    assert sheet.header["Instrument Type"] == "T1+"
    assert sheet.header["Date"] == "24/07/2026"


def test_data_rows_are_addressed_by_column_name_not_position(sheet):
    """The MGI [Data] section leads with `Lanes`, not `Sample_ID`.

    agr.seq.sample_sheet._get_field_index silently yields nothing on this sheet
    because it returns a row index and uses it as a column index - working on
    Illumina sheets only because Sample_ID happens to be column 0.
    """
    assert sheet.data_columns[0] == "Lanes"
    assert len(sheet.data) == 8  # 8 non-blank rows; the trailing blank rows are dropped
    assert sheet.data[0]["Sample_ID"] == "SQ5420"
    assert sheet.data[0]["index"] == "CTAGTGCTCT"
    assert sheet.data[0]["index2"] == "CCAACAGA"


def test_lanes_in_sample_sheet(sheet):
    assert lanes_in_sample_sheet(sheet) == ["L01", "L02", "L03", "L04"]


def test_samples_for_lane_selects_by_membership(sheet):
    assert [row["Sample_ID"] for row in samples_for_lane(sheet, 1)] == [
        "SQ5420",
        "SQ5421",
    ]
    assert [row["Sample_ID"] for row in samples_for_lane(sheet, 3)] == [
        "SQ5575",
        "SQ5576",
    ]


def test_lanes_by_library_drives_the_merge(sheet):
    """Libraries are NOT in every lane, so the merge is per library over its own lanes.

    A blanket merge of all four lanes would mix SQ5420's reads with SQ5575's.
    """
    assert lanes_by_library(sheet) == {
        "SQ5420": [1, 2],
        "SQ5421": [1, 2],
        "SQ5575": [3, 4],
        "SQ5576": [3, 4],
    }


def test_gbs_library_specs_carry_the_generate_keyfile_rows(sheet):
    """These are the redun cache key: a library reimports when its own rows change."""
    specs = gbs_library_specs(sheet)
    assert sorted(specs) == ["SQ5420", "SQ5421", "SQ5575", "SQ5576"]

    header, *rows = specs["SQ5420"]
    assert header[:3] == ["Sample_ID", "plateid", "labid"]
    assert len(rows) == 1
    assert rows[0][:5] == ["SQ5420", "13443", "GENOMNZ", "384", "PstI"]


def test_parse_lanes_expands_the_packed_digit_string():
    """`Lanes` is a digit string, not a lane number: "12" means L01 *and* L02."""
    assert parse_lanes("1") == [1]
    assert parse_lanes("12") == [1, 2]
    assert parse_lanes("34") == [3, 4]
    assert parse_lanes(" 12 ") == [1, 2]


@pytest.mark.parametrize("value", ["", "1,2", "1-2", "10", "L1", "abc"])
def test_parse_lanes_refuses_anything_it_has_not_been_validated_against(value):
    """Refused rather than guessed at.

    "10" in particular cannot be read as lane 10 in the packed encoding, and
    reading it as lanes 1 and 0 would be silently wrong.
    """
    with pytest.raises(MgiSampleSheetError):
        _ = parse_lanes(value)


def test_lane_label():
    assert lane_label(1) == "L01"
    assert lane_label(4) == "L04"


def test_missing_sheet_is_an_error():
    with pytest.raises(MgiSampleSheetError):
        _ = read_sample_sheet("/no/such/sample-sheet.csv")
