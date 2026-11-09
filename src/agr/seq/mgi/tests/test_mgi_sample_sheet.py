"""Tests for MGI sample sheet parsing, against the real DL100018469 sheet.
"""

import os.path
from dataclasses import replace

import pytest

from agr.seq.mgi.sample_sheet import (
    GENERATE_KEYFILE_SECTION,
    MgiSampleSheetError,
    check_flowcell,
    data_rows,
    gbs_library_specs,
    lane_label,
    lanes_by_library,
    lanes_in_sample_sheet,
    parse_lanes,
    read_sample_sheet,
    samples_for_lane,
    without_sections,
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


# --------------------------------------------------------------------------
# Cache keys: which edits re-demultiplex, which re-import which libraries
# --------------------------------------------------------------------------


def _edited_copy(tmp_path, old: str, new: str) -> str:
    with open(REFERENCE_SHEET) as f:
        content = f.read()
    assert content.count(old) == 1, "edit target must be unique: %s" % old
    path = os.path.join(str(tmp_path), "DL100018469.csv")
    with open(path, "w") as f:
        f.write(content.replace(old, new))
    return path


def _keys(sheet):
    return (
        without_sections(sheet, [GENERATE_KEYFILE_SECTION]),
        data_rows(sheet),
        gbs_library_specs(sheet),
    )


def test_without_sections_drops_only_generate_keyfile(sheet):
    view = without_sections(sheet, [GENERATE_KEYFILE_SECTION])
    assert GENERATE_KEYFILE_SECTION not in view.sections
    assert set(view.sections) == set(sheet.sections) - {GENERATE_KEYFILE_SECTION}
    assert view.data == sheet.data
    # the original is untouched
    assert GENERATE_KEYFILE_SECTION in sheet.sections


def test_without_sections_refuses_to_drop_data(sheet):
    with pytest.raises(ValueError):
        _ = without_sections(sheet, ["Data"])


def test_data_rows_is_the_data_section_with_its_header(sheet):
    rows = data_rows(sheet)
    assert rows[0] == sheet.data_columns
    assert len(rows) == len(sheet.data) + 1


def test_generate_keyfile_edit_changes_only_that_librarys_key(sheet, tmp_path):
    """Edits to [GenerateKeyfile] alone must not re-demultiplex, and only re-import
    the library whose rows changed."""
    edited = read_sample_sheet(
        _edited_copy(
            tmp_path,
            "SQ5421,13441,GENOMNZ,384,PstI,220-340",
            "SQ5421,13441,GENOMNZ,384,PstI,200-340",
        )
    )
    demux, data, specs = _keys(sheet)
    e_demux, e_data, e_specs = _keys(edited)

    # path differs between the copies; it is constant for a real run
    assert replace(e_demux, path=demux.path) == demux
    assert e_data == data
    assert {lib for lib in specs if specs[lib] != e_specs[lib]} == {"SQ5421"}


def test_data_edit_changes_the_demux_and_shared_import_keys(sheet, tmp_path):
    """A [Data] edit re-demultiplexes (where barcodes change) and re-imports every
    library, via the shared data_rows key."""
    edited = read_sample_sheet(_edited_copy(
            tmp_path,
            "1,SQ5420,SQ5420_Deer_Goat_PstI,NS07,,,UDP0007,CTAGTGCTCT",
            "1,SQ5420,SQ5420_Deer_Goat_PstI,NS07,,,UDP0007,CTAGTGCTCA",
        ))
    demux, data, specs = _keys(sheet)
    e_demux, e_data, e_specs = _keys(edited)

    assert replace(e_demux, path=demux.path) != demux
    assert e_data != data
    assert e_specs == specs


def test_check_flowcell_accepts_the_sheets_own_run(sheet):
    check_flowcell(sheet, "DL100018469")  # must not raise


def test_check_flowcell_refuses_a_sheet_for_another_run(sheet):
    """A sheet copied from a template can carry the wrong Flowcell yet still fit the
    run's barcodes; caught at launch rather than at keyfile import, hours later."""
    with pytest.raises(MgiSampleSheetError, match="Flowcell is DL100018469 but the run is DL100099999"):
        check_flowcell(sheet, "DL100099999")


def test_check_flowcell_refuses_a_sheet_with_no_flowcell(sheet):
    no_header = replace(sheet, sections={**sheet.sections, "Header": []})
    with pytest.raises(MgiSampleSheetError, match="no Flowcell"):
        check_flowcell(no_header, "DL100018469")
