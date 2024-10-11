# sample sheet helpers

import csv
import datetime
import re
from enum import Enum
from typing import Optional, Generator


class SampleSheetError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        if self._e is None:
            return self._msg
        else:
            return "%s: %s" % (self._msg, str(self._e))


class SampleSheetSection:
    """A sample sheet section name is a word in square brackets."""

    name_re = re.compile(r"^\[(\w*)\]$")

    @staticmethod
    def name_if_section_header(row: list[str]) -> Optional[str]:
        """Return section name if this row starts a new section, otherwise None.  The section name does not include the brackets."""
        if len(row) > 0 and (m := SampleSheetSection.name_re.match(row[0])) is not None:
            return m.group(1)
        return None

    def __init__(self, name: str, rows: list[list[str]] = []):
        self._name = name
        self._rows: list[list[str]] = []
        for row in rows:
            self.append_harmonised(row)

    @property
    def name(self) -> str:
        return self._name

    @property
    def rows(self) -> list[list[str]]:
        return self._rows

    def named_column(self, column_name: str) -> Optional[list[str]]:
        """If the first row contains the (case-insensitive) named column, return as a list all the values from that column, otherwise None."""
        if not self._rows:
            return None
        try:
            lowercase_header = [s.lower() for s in self.rows[0]]
            column_index = lowercase_header.index(column_name.lower())
        except ValueError:
            return None
        return [row[column_index] for row in self._rows[1:]]

    def append_harmonised(self, row: list[str]):
        """Read a row into the sample sheet section, with on-the-fly harmonisation.

        The following harmonisations are performed:
        - any occurrence of 'Adapter' in the Settings section is replaced with `AdapterRead1`
        """
        harmonised = row
        if self.name.casefold() == "Settings".casefold():
            if len(row) >= 1 and row[0].casefold() == "Adapter".casefold():
                harmonised = ["AdapterRead1"] + harmonised[1:]
        self._rows.append(harmonised)

    def get1(self, row_name: str):
        """Return element 1 from row by name, or None if not found."""
        return next(
            (
                row[1]
                for row in self._rows
                if row and row[0].casefold() == row_name.casefold() and len(row) >= 1
            ),
            None,
        )

    # TODO this may not be required after all, consider removing
    def set1(self, row_name: str, value: str):
        """Set element 1 from row by name, appending a new row if not found."""
        if (
            row := next(
                (
                    row
                    for row in self._rows
                    if row and row[0].casefold() == row_name.casefold()
                ),
                None,
            )
        ) is not None:
            if len(row) >= 1:
                row[1] = value
            else:
                row.append(value)
        else:
            self._rows.append([row_name, value])

    def _get_field_index(self, field_name: str) -> Optional[int]:
        """Return index of named field if found in the first row, presumed to be field names, otherwise None if not found."""
        return next(
            (
                i
                for i, row in enumerate(self._rows)
                if row[0].casefold() == field_name.casefold()
            ),
            None,
        )

    def get_fields(
        self, field_names: list[str]
    ) -> Generator[list[Optional[str]], None, None]:
        """Return the named fields from each row, if any."""
        field_indices = [
            self._get_field_index(field_name) for field_name in field_names
        ]
        # row[0] is the field names, so start at 1 for the values
        for row in self._rows[1:]:
            candidate = [
                row[i] if i is not None and len(row) > i else None
                for i in field_indices
            ]
            if any(candidate):
                yield candidate

    @property
    def num_cols(self):
        """Return number of columns in the section, including what is required for the name."""
        return max(1, max((len(row) for row in self._rows), default=0))

    def write(self, csvwriter, num_cols):
        """Write out the sample sheet section in `num_cols` columns, which may be greater than our `num_cols` because of other sections."""
        csvwriter.writerow(["[%s]" % self.name] + [""] * (num_cols - 1))
        for row in self._rows:
            csvwriter.writerow(row + [""] * (num_cols - len(row)))


_standard_header = [
    SampleSheetSection(
        "Header",
        [
            ["IEMFileVersion", "4"],
            ["Date", datetime.date.today().strftime("%d/%m/%Y")],
            ["Workflow", "GenerateFASTQ"],
            ["Application", "HiSeq FASTQ Only"],
            ["Assay", "TruSeq HT"],
            ["Description", ""],
            ["Chemistry", "Amplicon"],
            [],
        ],
    ),
    SampleSheetSection("Reads", [["101"], []]),
    SampleSheetSection(
        "Settings",
        [
            ["ReverseComplement", "0"],
            ["Adapter", "AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"],
            ["AdapterRead2", "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"],
            [],
        ],
    ),
    SampleSheetSection("Data"),
]


class SampleSheet:
    """Abstracted access to sample sheets, including santization.

    Sanitization is performed at read time, so that first time access to a sample sheet is
    the same as after-the-event access to the harmonized sample sheet."""

    def __init__(
        self,
        path: str,
        impute_lanes: Optional[list[int]] = None,
    ):
        self._path = path
        self._impute_lanes = impute_lanes
        self._sections = self._read(path)
        self._section_indices = {
            s.name.casefold(): i for i, s in enumerate(self._sections)
        }
        self._validate(path)
        self._infer_sequencing_type(path)
        self._fastq_files = self._get_fastq_filenames()
        # print(
        #     "SampleSheet sequencing type: %s, fastq files: %s"
        #     % (self._sequencing_type, ", ".join(self._fastq_files))
        # )

    @property
    def path(self):
        return self._path

    @property
    def fastq_files(self):
        return self._fastq_files

    def _read(self, path: str):
        """Read a sample sheet into its sections"""
        self._line = 0
        sections = []
        try:
            with open(path) as csvfile:
                csvreader = csv.reader(csvfile)

                for row in csvreader:
                    self._line += 1
                    if (
                        name := SampleSheetSection.name_if_section_header(row)
                    ) is not None:
                        sections.append(SampleSheetSection(name))
                    else:
                        if not sections:
                            # if there's no header then prepend a standard one, defined above
                            sections = _standard_header
                        sections[-1].append_harmonised(row)
                self._line = None
                return sections

        except OSError as e:
            raise SampleSheetError("can't read sample sheet at %s" % path, e)

    def _raise_error(self, msg: str, e: Optional[Exception] = None):
        file_location = (
            "%s:%d" % (self._path, self._line) if self._line is not None else self._path
        )
        raise SampleSheetError("%s in sample sheet at %s" % (msg, file_location), e)

    def _validate(self, path: str):
        """Check certain properties in the sample sheet."""
        if (settings := self.get_section("Settings")) is None:
            self._raise_error("missing Settings section")
        elif settings.get1("AdapterRead1") is None:
            raise SampleSheetError(
                "sample sheet at %s Settings section is missing AdapterRead1 field"
                % path
            )

    def _infer_sequencing_type(self, path: str):
        """Infer the sequencing type from the Reads section.

        TODO confirm this logic is correct
        """
        if (reads := self.get_section("Reads")) is None:
            raise SampleSheetError(
                "missing Reads section from sample sheet at %s" % path
            )
        reads_values = [row[0] for row in reads.rows if row and row[0]]
        n_reads_values = len(reads_values)
        self._sequencing_type = (
            SequencingType.SINGLE_END
            if n_reads_values == 1
            else (
                SequencingType.PAIRED_END
                if n_reads_values == 2
                else self._raise_error(
                    "unexpected number of read values: %d" % n_reads_values
                )
            )
        )

    def _get_fastq_filenames(
        self,
    ) -> set[str]:
        """
        Construct expected fastq.gz filenames from sample sheet.
        """
        predicted_files = set()
        reads = [1, 2] if self._sequencing_type == SequencingType.PAIRED_END else [1]
        sample_id_number = {}

        if (data := self.get_section("Data")) is None:
            self._raise_error("missing Data section")
        else:
            for lane, sample_id in data.get_fields(["Lane", "Sample_ID"]):
                if lane is None:
                    lane = 1  # default lane to 1
                isample = sample_id_number.get(sample_id, None)
                if isample is None:
                    isample = len(sample_id_number) + 1
                    sample_id_number[sample_id] = isample

                    # use the lane as in the sample sheet, unless impute-lanes has been passed in, in which case, use those
                    lanes = [lane] if self._impute_lanes is None else self._impute_lanes
                    for lane in lanes:
                        for i_read in reads:
                            predicted_files.add(
                                "%s_S%d_L%03d_R%d_001.fastq.gz"
                                % (
                                    sample_id,
                                    isample,
                                    lane,
                                    i_read,
                                )
                            )

        return predicted_files

    def get_section(self, name: str) -> Optional[SampleSheetSection]:
        if (i := self._section_indices[name.casefold()]) is not None:
            return self._sections[i]
        else:
            return None

    def write(self, path: str):
        """Write sample sheet."""
        with open(path, "w") as csvfile:
            csvwriter = csv.writer(csvfile)
            num_cols = max((section.num_cols for section in self._sections), default=0)
            for section in self._sections:
                section.write(csvwriter, num_cols)


class SequencingType(Enum):
    SINGLE_END = 1
    PAIRED_END = 2
