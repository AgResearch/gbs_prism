"""MGI (DNBSEQ) sample sheet parsing.

Ported from `mgi_prism/workflow/scripts/process_samplesheet.py`, which is
stdlib-only and `NamedTuple`-based because bare python3 on the eRI compute nodes is
3.6.8. gbs_prism runs 3.12, so the style is modernised; the logic is not.

**Keep this module stdlib-only.** CI (`nix run '.#tests'`) builds python plus pytest
and nothing else, so anything importing gquery, redun or pydantic fails at
collection - see CLAUDE.md.

Two structural differences from the Illumina sheets `agr.seq.sample_sheet` handles:

* an MGI sheet has no `[Settings]` section, so the Illumina parser rejects it
  outright;
* its `[Data]` section leads with `Lanes`, not `Sample_ID`. Columns are therefore
  addressed by name here, never by position.

The sheet also lives *outside* the run tree, at `<sample_sheet_root>/<flowcell>.csv`
- gquery's `Mgi.derive_run_name_from_sample_sheet` cross-checks `[Header] Flowcell`
against that filename stem, so the two must agree.
"""

import csv
import os.path
import re
from dataclasses import dataclass, field

_SECTION_RE = re.compile(r"^\[(?P<name>[^\]]+)\]")

# Both spellings occur in production sheets: DL100018469 and DL100018479 use
# "Lanes", DL100018216 uses "Lane". gquery's Mgi accepts both for the same reason.
LANE_COLUMNS = ("Lanes", "Lane")
SAMPLE_ID_COLUMNS = ("Sample_ID", "SampleID", "Sample_Name")
INDEX_COLUMNS = ("index", "Index", "I7_Index", "index1")
INDEX2_COLUMNS = ("index2", "Index2", "I5_Index")

GENERATE_KEYFILE_SECTION = "GenerateKeyfile"


class MgiSampleSheetError(Exception):
    """Raised for any MGI sample sheet the pipeline refuses to process."""


class SkippedLaneError(MgiSampleSheetError):
    """Every sample in a lane has no index, so there is nothing to demultiplex on.

    A subclass so callers can skip *just* that lane while any other sample sheet
    failure stays fatal: unlike a wrong offset or a mismatched sheet/run pair, a
    lane with no barcodes is a data-completeness gap local to that lane.
    """


@dataclass(frozen=True)
class MgiSampleSheet:
    """A parsed MGI sample sheet.

    `sections` keeps every section verbatim - `Header`, `Reads`, `Data`,
    `GenerateKeyfile` - so callers can reach sections this module does not
    interpret. Only `[Data]` is promoted to dictionaries.
    """

    path: str
    sections: dict[str, list[list[str]]]
    data: list[dict[str, str]]
    data_columns: list[str] = field(default_factory=list)

    @property
    def header(self) -> dict[str, str]:
        """`[Header]` as key -> value (e.g. `Flowcell`, `Instrument Type`)."""
        return {
            row[0]: (row[1] if len(row) > 1 else "")
            for row in self.sections.get("Header", [])
            if row and row[0]
        }

    @property
    def flowcell(self) -> str:
        """`[Header] Flowcell`, which for MGI is also the run name."""
        flowcell = self.header.get("Flowcell", "").strip()
        if not flowcell:
            raise MgiSampleSheetError("%s: [Header] has no Flowcell" % self.path)
        return flowcell


def read_sample_sheet(path: str) -> MgiSampleSheet:
    """Parse an MGI sample sheet into sections plus typed `[Data]` rows.

    Copes with both platforms' quirks: T1+ sheets are CRLF with stray leading
    spaces in values, G99 sheets are LF, and the two carry different columns.
    Every field is stripped.
    """
    if not os.path.exists(path):
        raise MgiSampleSheetError("sample sheet does not exist: %s" % path)

    # A plain dict preserves insertion order, so the sheet's section order survives
    # without tracking it separately.
    sections: dict[str, list[list[str]]] = {}
    current: str | None = None

    # newline="" lets csv handle the CRLF sheets without leaving stray \r;
    # utf-8-sig strips a BOM if one is present.
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        for raw in csv.reader(f):
            row = [cell.strip() for cell in raw]
            if not any(row):
                continue
            if (match := _SECTION_RE.match(row[0])) is not None:
                current = match.group("name").strip()
                _ = sections.setdefault(current, [])
                continue
            if current is None:
                raise MgiSampleSheetError(
                    "%s: content before the first [Section] header: %s" % (path, row)
                )
            sections[current].append(row)

    if "Data" not in sections:
        raise MgiSampleSheetError("%s: no [Data] section found" % path)
    if not sections["Data"]:
        raise MgiSampleSheetError("%s: [Data] section is empty" % path)

    columns = sections["Data"][0]
    data = [
        # Pad rather than let zip drop short rows: a missing trailing field should
        # read as empty, not shift every column left.
        dict(zip(columns, list(row) + [""] * (len(columns) - len(row))))
        for row in sections["Data"][1:]
    ]

    if not data:
        raise MgiSampleSheetError(
            "%s: [Data] section has a header but no sample rows" % path
        )

    return MgiSampleSheet(
        path=path, sections=sections, data=data, data_columns=columns
    )


def column(sheet: MgiSampleSheet, *candidates: str) -> str:
    """Resolve the first present `[Data]` column name, case-insensitively."""
    lowered = {name.lower(): name for name in sheet.data_columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    raise MgiSampleSheetError(
        "%s: [Data] has none of the expected columns %s; found %s"
        % (sheet.path, list(candidates), sheet.data_columns)
    )


def optional_column(sheet: MgiSampleSheet, *candidates: str) -> str | None:
    try:
        return column(sheet, *candidates)
    except MgiSampleSheetError:
        return None


def parse_lanes(value: str) -> list[int]:
    """Expand a `Lanes` field, which is a **digit string**.

    `"12"` -> `[1, 2]`, `"34"` -> `[3, 4]`, `"1"` -> `[1]`. This is membership, not
    equality: a row with `Lanes=12` belongs to L01 *and* L02.

    Anything but non-zero digits is refused rather than guessed at - comma- and
    dash-separated sheets have not been validated against. `"10"` is refused too:
    the packed encoding cannot express lane 10, and reading it as lanes 1 and 0
    would be silently wrong. T1+ has four lanes, so that is a documented limit of
    the format rather than a live constraint.
    """
    text = (value or "").strip()
    if not text:
        raise MgiSampleSheetError("empty Lanes field")
    if not text.isdigit():
        raise MgiSampleSheetError(
            "Lanes field %r is not a digit string; expected e.g. '1', '12', '34'"
            % value
        )
    lanes = sorted({int(char) for char in text})
    if any(lane == 0 for lane in lanes):
        raise MgiSampleSheetError("Lanes field %r contains lane 0" % value)
    return lanes


def lane_label(lane: int) -> str:
    """`1` -> `"L01"`."""
    return "L%02d" % lane


def lane_number(lane: int | str) -> int:
    """Accept `"L01"`, `"l01"`, `"1"` or `1` and return `1`."""
    if isinstance(lane, int):
        return lane
    text = lane.strip()
    if text[:1].upper() == "L":
        text = text[1:]
    if not text.isdigit():
        raise MgiSampleSheetError("cannot interpret lane %r" % lane)
    return int(text)


def lanes_in_sample_sheet(sheet: MgiSampleSheet) -> list[str]:
    """Sorted, deduplicated lane labels across every `[Data]` row."""
    lane_column = column(sheet, *LANE_COLUMNS)
    found: set[int] = set()
    for row in sheet.data:
        found.update(parse_lanes(row[lane_column]))
    return [lane_label(lane) for lane in sorted(found)]


def samples_for_lane(sheet: MgiSampleSheet, lane: int | str) -> list[dict[str, str]]:
    """`[Data]` rows belonging to `lane` - by digit membership, not equality."""
    wanted = lane_number(lane)
    lane_column = column(sheet, *LANE_COLUMNS)
    rows = [row for row in sheet.data if wanted in parse_lanes(row[lane_column])]
    if not rows:
        raise MgiSampleSheetError(
            "%s: no samples for lane %s; lanes present: %s"
            % (sheet.path, lane_label(wanted), ", ".join(lanes_in_sample_sheet(sheet)))
        )
    return rows


def lanes_by_library(sheet: MgiSampleSheet) -> dict[str, list[int]]:
    """Which lanes each library was sequenced in.

    This drives the merge, and it is why the merge cannot be a blanket join of every
    lane: in the reference run SQ5420/SQ5421 are in L01+L02 while SQ5575/SQ5576 are
    in L03+L04, so merging all four would mix unrelated libraries' reads.

    Each lane's own `BioInfo.csv` records the same mapping as `DNBID_L<n>`, which is
    a useful cross-check, but the sheet is authoritative.
    """
    id_column = column(sheet, *SAMPLE_ID_COLUMNS)
    lane_column = column(sheet, *LANE_COLUMNS)

    lanes: dict[str, set[int]] = {}
    for row in sheet.data:
        library = row[id_column].strip()
        if not library:
            continue
        lanes.setdefault(library, set()).update(parse_lanes(row[lane_column]))
    return {library: sorted(found) for library, found in lanes.items()}


def gbs_library_specs(sheet: MgiSampleSheet) -> dict[str, list[list[str]]]:
    """Per-library rows from the `[GenerateKeyfile]` section.

    Maps library name to the section's header row followed by that library's own
    data rows. This is redun's cache key for keyfile import: when a library's
    metadata changes its rows change, re-running only that library's task.

    Same shape as the Illumina `get_gbs_library_specs` it replaces, so the keyfile
    tasks consume it unchanged.
    """
    rows = sheet.sections.get(GENERATE_KEYFILE_SECTION)
    if not rows:
        return {}

    header = rows[0]
    try:
        sample_id_index = [name.lower() for name in header].index("sample_id")
    except ValueError:
        raise MgiSampleSheetError(
            "%s: [%s] section has no Sample_ID column (found %s)"
            % (sheet.path, GENERATE_KEYFILE_SECTION, header)
        )

    specs: dict[str, list[list[str]]] = {}
    for row in rows[1:]:
        if sample_id_index >= len(row) or not row[sample_id_index].strip():
            continue
        specs.setdefault(row[sample_id_index], [header]).append(row)
    return specs


def index_pairs(sheet: MgiSampleSheet, lane: int | str) -> list[tuple[str, str]]:
    """`[(index, index2), ...]` for one lane, in sheet order.

    Rows with no index are dropped: such a row is usually a bookkeeping gap - an
    App-barcoded control never written into the sheet - rather than evidence the
    lane is misread. `barcode_entries` is where that warns. Dropping them here also
    keeps them from tripping the mixed-index-length check on their empty values.
    """
    rows = samples_for_lane(sheet, lane)
    index_column = column(sheet, *INDEX_COLUMNS)
    index2_column = optional_column(sheet, *INDEX2_COLUMNS)

    barcoded = [row for row in rows if row[index_column].strip()]
    if not barcoded:
        raise SkippedLaneError(
            "%s: lane %s has no samples with barcodes - every row has an empty index"
            % (sheet.path, lane_label(lane_number(lane)))
        )

    return [
        (
            row[index_column].strip().upper(),
            row.get(index2_column, "").strip().upper() if index2_column else "",
        )
        for row in barcoded
    ]
