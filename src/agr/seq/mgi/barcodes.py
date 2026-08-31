"""MGI barcode geometry for `splitBarcode`, and the layout check that confirms it.

Ported from `mgi_prism/workflow/scripts/process_samplesheet.py` - the logic is
unchanged, the style is modernised for 3.12. **Keep this module stdlib-only**: CI
builds python plus pytest and nothing else.

Design principle: **fail loudly**. A wrong barcode offset produces a run that looks
successful while sending ~100% of reads to `undecoded`, so nothing here guesses.
Geometry comes from the run's own `BioInfo.csv`, every derived value is
cross-checked against the reads, and anything inconsistent raises.

**Where the -b arguments come from.** The per-lane `BioInfo.csv`. The two platforms
use different keys - T1+ `Read1Len`/`Read2Len`/`BarcodeLen`/`DualBarcodeLen`, G99
`Read1 Cycles`/`Read2 Cycles`/`Barcode`/`Dual Barcode` - and sequence the two
barcode blocks in *opposite* order, which G99 states as
`Sequence Order,Read1-Read2-Dualbarcode-Barcode` and T1+ leaves implicit (Barcode
first). Reading that order gives one rule for both platforms:

    the sample sheet's `index` is the **first** barcode block on the machine,
    `index2` the **second**

which looks inverted if the key names are compared alone. Verified against hand-made
ground truth: G99 `FT150034703` -> `-b 100 8 1 -b 108 10 1`, T1+ `DL100018479` ->
`-b 100 10 1 -b 110 8 1`.

**The anchor** is the one thing `BioInfo.csv` will not give, so it comes from the
reads: the barcode blocks sit at the *end* of the read, so it is
`read_length - total barcode cycles`. The declared value is only a cross-check,
because G99 overstates it by exactly one cycle (`Read1 Cycles,101` for a 100-cycle
read) and anchoring on it sends the whole lane to `undecoded`.

**Orientation** (whether the reads carry the indices forward or reverse-complemented)
and **slot order** (which index was sequenced first) are *derived* from SE-vs-PE by
`derive_layout`, not searched for. `verify_layout` then confirms that choice against
the reads, scoring it against its reverse-strand sibling so a mislabelled or
MGI-native run aborts loudly rather than mis-decoding.

`oriented_barcode` absorbs orientation and slot order into the barcode file's
*content*, so the `-b` offsets always come straight from geometry.
"""

import collections
import csv
import gzip
import logging
import os.path
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace

from agr.seq.mgi.sample_sheet import (
    INDEX_COLUMNS,
    INDEX2_COLUMNS,
    SAMPLE_ID_COLUMNS,
    MgiSampleSheet,
    SkippedLaneError,
    column,
    index_pairs,
    lane_label,
    lane_number,
    optional_column,
    samples_for_lane,
)

logger = logging.getLogger(__name__)

# Reads that must carry a listed barcode before the derived layout is accepted.
# An ABSOLUTE count, not a fraction of the reads scanned: the sheet defines the
# batch, so the expected set shrinks when an operator carves a batch out of a lane
# while the reads scanned are always the whole lane's. A rate would therefore
# measure the batch's share of its lane, not whether the layout is right.
#
# 50 sits far above chance and far below the smallest legitimate batch: a random
# 18-base string matches one of 3788 listed barcodes with probability ~5.5e-8.
# Calibration on FT150034703 L01 (3788 samples) at the correct offsets: the full
# sheet reaches 50 hits in 59 reads, an 8-sample subset in 30461, a single sample
# in 221809.
DEFAULT_MIN_HITS = 50

# Where the scan gives up and refuses. Bounds the cost of a genuine failure: a
# mismatched sheet/run pair accumulates hits at chance, so it can only stop here
# (~1.5s warm). Also the knob to raise for a batch of unusually low-yield samples -
# the one legitimate case that can fail this gate.
DEFAULT_MAX_SCAN_READS = 500000

# Reads retained for the failure diagnostic. The observed-barcode census and the
# sheet-transform panel are both computed from this bounded sample rather than from a
# second pass over the fastq, so a diagnosis costs no extra decompression. The top of
# the census is stable long before the cap: measured on FT150034703 L01, 21k reads
# already carry 5778 distinct barcodes and the ranking has settled.
DIAGNOSTIC_SAMPLE_READS = 20000

# Rows shown in the census table. A GBS lane spreads its reads over thousands of
# barcodes, so the operator needs a legible top, not the distribution.
CENSUS_TOP_N = 20

# Where the *coverage* scan stops. Reaching min_hits proves the layout; seeing every
# listed barcode is a far deeper question, because per-sample yield has a long tail.
# Measured on FT150034703 L01 (3788 rows): 5x coverage still leaves 172 rows unseen on a
# perfectly healthy lane, 40x leaves 8, and all 3788 appear only at 679k reads (2.1s).
# So coverage is scanned to exhaustion rather than to a multiple of the row count, and
# this caps the lane where some rows genuinely never appear. The 96-row PE lane
# DL100018466 needed 379k reads (1.5s) for the same reason - small sheets have the tail
# too.
#
# The cap is what a lane with a genuinely dead sample costs, because coverage can then
# never complete and the scan always runs to here. Measured on that lane's read 2 (the
# 60 GB PE file, the worst case in production): 1M reads in 3.6s. Against a stage 1 that
# goes on to run a ~25 minute splitBarcode job per lane, that is affordable even on a
# fully cached rerun.
COVERAGE_MAX_SCAN_READS = 1000000

# Reads per scan chunk and - first chunk only - the window the modal read length is
# taken over. That window IS the anchor, so a narrower one picking a different modal
# length on a lane with truncated reads would move every -b argument. The first
# chunk is also a floor: the modal length must be established before anything can be
# counted, so a lower max_scan_reads cannot undercut it.
SCAN_CHUNK_READS = 2000

# splitBarcode's -b startCycle is 0-based, lining up exactly with a Python string
# index, so derived offsets pass through unadjusted.
#
# In paired-end mode the barcode blocks follow read 2, and splitBarcode counts -b
# across the *concatenated* read, not from the start of read 2. Measured on
# DL100018466 L01 (1M read pairs): -b 300/310 decodes 79.394%, -b 150/160 decodes
# 0.0001%. Shifting the offsets is therefore the whole mechanism.
#
# ⚠️ No read1-length flag is emitted. `mgi_prism` passes `-p <read1 length>` and
# records it as inert on 2.0.0-4 (same 79.394% either way); reading the binary's own
# usage explains why - there is no lowercase `-p` at all, and the uppercase `-P INT`
# (`set PE mode, INT is read1Length`) is documented under the **cal-file** mode
# (`-F`), not the fastq mode (`-1`) this pipeline uses. So it was being ignored.
# Passing an unrecognised flag to state an intent it does not carry is worse than
# passing nothing. If a PE MGI run is ever processed here, `-P` is the candidate to
# measure - but the concatenated offsets above are what was actually verified to work.
PE_OFFSET_READ2_RELATIVE = "read2-relative"
PE_OFFSET_CONCATENATED = "concatenated"
PE_OFFSET_BASES = (PE_OFFSET_READ2_RELATIVE, PE_OFFSET_CONCATENATED)

_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")
_VALID_BASES = set("ACGTN")

FORWARD = "forward"
REVCOMP = "revcomp"

# Which of the sheet's two indices the instrument sequenced *first*. Not stated in
# BioInfo.csv; for Illumina-converted libraries it follows deterministically from
# SE-vs-PE - see derive_layout.
INDEX_FIRST = "index-first"
INDEX2_FIRST = "index2-first"
SLOT_ORDERS = (INDEX_FIRST, INDEX2_FIRST)

# Library prep, which fixes how the barcode region is laid down and read.
# Illumina-converted is the only characterised convention; MGI-native is a named
# stub so an unsupported run fails with a pointer rather than a wrong guess.
LIBRARY_TYPE_ILLUMINA = "illumina-converted"
LIBRARY_TYPE_MGI = "mgi-native"
LIBRARY_TYPES = (LIBRARY_TYPE_ILLUMINA, LIBRARY_TYPE_MGI)

# The only two physically possible (orientation, slot order) layouts for an
# Illumina-converted library: the top strand read forward (SE), and its exact
# reverse complement read off the other strand (PE read 2). verify_layout scores
# both, so a run whose reads match the *opposite* strand aborts with a specific
# diagnosis rather than a generic low hit rate.
_COHERENT_LAYOUTS = (
    ((FORWARD, FORWARD), INDEX_FIRST),
    ((REVCOMP, REVCOMP), INDEX2_FIRST),
)

# Both platforms sequence the insert first and the barcode cycles last (T1+ says so
# as BarcodePosition,BarcodePosEnd), but differ in which barcode block comes first.
# Read the order from the file where it states it; default to T1+'s convention where
# it does not.
BARCODE = "Barcode"
DUAL_BARCODE = "DualBarcode"
_T1_BLOCK_ORDER = (BARCODE, DUAL_BARCODE)

# Key aliases, normalised (lowercased, non-alphanumerics dropped) so that
# "Read1Len", "Read1 Cycles" and "read1_len" all resolve.
_BIOINFO_KEYS = {
    "read1_len": ("read1len", "read1cycles"),
    "read2_len": ("read2len", "read2cycles"),
    "barcode_len": ("barcodelen", "barcode"),
    "dual_barcode_len": ("dualbarcodelen", "dualbarcode"),
    "sequence_order": ("sequenceorder",),
    "machine_id": ("machineid",),
}


class BarcodeLayoutError(Exception):
    """Raised when the barcode layout cannot be established or confirmed."""


class BioInfoError(Exception):
    """Raised when a run's BioInfo.csv is missing, unreadable or incomplete."""


def revcomp(seq: str) -> str:
    """Reverse complement of an IUPAC-free (ACGTN) sequence."""
    return seq.translate(_COMPLEMENT)[::-1]


def _oriented(seq: str, orientation: str) -> str:
    return seq if orientation == FORWARD else revcomp(seq)


def derive_layout(
    is_pe: bool, library_type: str = LIBRARY_TYPE_ILLUMINA
) -> tuple[tuple[str, str], str]:
    """`(orientation, slot_order)` from sequencing mode plus library prep.

    For an **Illumina-converted** library the sheet's indices are forward-native and
    the barcode region is one block, `5'-[i7][i5]-3'`. Only the strand carrying the
    read changes:

    * **SE** reads the top strand directly -> `i7 + i5` forward
      -> `((FORWARD, FORWARD), INDEX_FIRST)`;
    * **PE** read 2 reads the complementary strand -> `rc(i5) + rc(i7)`
      -> `((REVCOMP, REVCOMP), INDEX2_FIRST)`.

    Being exact reverse complements (`rc(i7+i5) == rc(i5)+rc(i7)`) is why only these
    two are physically possible. Verified two independent ways, so it is derived
    here rather than searched for; the reads only *verify* the choice.
    """
    if library_type == LIBRARY_TYPE_MGI:
        raise NotImplementedError(
            "MGI-native barcode convention is not yet characterised; only "
            "Illumina-converted libraries are supported. Extend derive_layout()."
        )
    if library_type != LIBRARY_TYPE_ILLUMINA:
        raise BarcodeLayoutError("unknown library type %r" % library_type)
    if is_pe:
        return (REVCOMP, REVCOMP), INDEX2_FIRST
    return (FORWARD, FORWARD), INDEX_FIRST


def _slot_lengths(index_len: int, index2_len: int, slot_order: str) -> tuple[int, int]:
    """`(slot 1, slot 2)` index lengths, in the order the machine read them.

    A single-index lane (`index2_len == 0`) has one slot regardless of order: the PE
    derivation hands it `index2-first`, which must still collapse to `index` at slot
    1 rather than a zero-length first -b.
    """
    if not index2_len:
        return index_len, 0
    if slot_order == INDEX2_FIRST:
        return index2_len, index_len
    return index_len, index2_len


def oriented_barcode(
    index: str, index2: str, orientation: tuple[str, str], slot_order: str
) -> str:
    """The barcode string as the instrument writes it, slot 1 then slot 2.

    One place decides how a sheet row becomes a read's barcode, so the `-B` file and
    the layout scoring in `verify_layout` cannot drift apart.

    (splitBarcode's `-r` flag is deliberately unused: it applies to the whole
    concatenated barcode and cannot express a per-index difference.)
    """
    first = _oriented(index, orientation[0])
    second = _oriented(index2, orientation[1])
    if slot_order == INDEX2_FIRST:
        return second + first
    return first + second


def sheet_indices(
    barcode: str,
    orientation: tuple[str, str],
    slot_order: str,
    index_len: int,
    index2_len: int,
) -> tuple[str, str]:
    """`(index, index2)` as the *sample sheet* carries them, from a read's barcode.

    The exact inverse of `oriented_barcode`, and deliberately adjacent to it: every
    barcode this module quotes back to an operator passes through here, so an observed
    barcode is reported in the complement and column order they would type into the
    sheet - not in the orientation the instrument happened to write it.

    Getting this wrong is **silent, not loud**. Real sheets pair i7/i5 combinatorially,
    so on the verified run DL100018466 every sample's `(index, index2)` also appears as
    some *other* sample's `(index2, index)`: dropping the INDEX2_FIRST swap re-labels
    100% of decodable reads as a different, real sample and never once produces an
    invalid-looking barcode. That is why this is pinned by a round-trip test against
    that run's own barcode file rather than by inspection.
    """
    slot1_len, slot2_len = _slot_lengths(index_len, index2_len, slot_order)
    slot1 = barcode[:slot1_len]
    slot2 = barcode[slot1_len : slot1_len + slot2_len]

    # A single-index lane has one slot whichever order was derived: _slot_lengths
    # collapses to (index_len, 0) and oriented_barcode leaves the index in slot 1 even
    # under INDEX2_FIRST. Swapping here would report it in the index2 column.
    if not slot2_len:
        return _oriented(slot1, orientation[0]), ""

    first, second = (slot2, slot1) if slot_order == INDEX2_FIRST else (slot1, slot2)
    return _oriented(first, orientation[0]), _oriented(second, orientation[1])


# --------------------------------------------------------------------------
# Barcode entries - the -B file
# --------------------------------------------------------------------------


def _sheet_columns(sheet: MgiSampleSheet) -> tuple[str, str, str | None]:
    """`(Sample_ID, index, index2)` column names, resolved once.

    Shared so the barcode file and the sample-name lookup below cannot disagree about
    which column is which - the spellings vary between T1+ and G99 sheets.
    """
    return (
        column(sheet, *SAMPLE_ID_COLUMNS),
        column(sheet, *INDEX_COLUMNS),
        optional_column(sheet, *INDEX2_COLUMNS),
    )


def sample_ids_by_index(sheet: MgiSampleSheet, lane: int | str) -> dict[tuple[str, str], str]:
    """`{(index, index2): sample name}` for one lane.

    Only for labelling diagnostics. `index_pairs` deliberately drops the sample name,
    but a census row or an unobserved barcode is far more actionable with it: an
    operator can go straight to the offending row instead of grepping their own sheet.

    Two rows sharing a barcode is a collision the demultiplexer would suffer from
    anyway, so they are joined rather than one silently winning.
    """
    id_column, index_column, index2_column = _sheet_columns(sheet)
    names: dict[tuple[str, str], list[str]] = {}
    for row in samples_for_lane(sheet, lane):
        index = row[index_column].strip().upper()
        if not index:
            continue
        index2 = (row.get(index2_column, "") or "").strip().upper() if index2_column else ""
        names.setdefault((index, index2), []).append(row[id_column].strip())
    return {pair: ", ".join(ids) for pair, ids in names.items()}


def _validate_index(seq: str, what: str, sample_id: str) -> str:
    upper = seq.strip().upper()
    if bad := set(upper) - _VALID_BASES:
        raise BarcodeLayoutError(
            "sample %s: %s contains non-ACGTN characters %s: %r"
            % (sample_id, what, sorted(bad), seq)
        )
    return upper


def barcode_entries(
    sheet: MgiSampleSheet,
    lane: int | str,
    orientation: tuple[str, str] = (FORWARD, FORWARD),
    slot_order: str = INDEX_FIRST,
) -> list[tuple[str, str]]:
    """`[(sample_id, slot 1 + slot 2), ...]` for one lane.

    The two indices concatenated in `-b` order, which is what `splitBarcode -B`
    expects: `Sample_ID<TAB>barcode`, headerless and tab-delimited. Single-index
    lanes collapse to just `index`.

    Everything the run does differently from the sheet is absorbed here, in the
    barcode file's *content*, so the `-b` offsets stay as the geometry gives them.
    """
    if slot_order not in SLOT_ORDERS:
        raise BarcodeLayoutError(
            "slot_order must be one of %s, got %r" % (list(SLOT_ORDERS), slot_order)
        )

    rows = samples_for_lane(sheet, lane)
    id_column, index_column, index2_column = _sheet_columns(sheet)

    entries: list[tuple[str, str]] = []
    lengths: set[tuple[int, int]] = set()
    seen: set[str] = set()

    for row in rows:
        sample_id = row[id_column].strip()
        if not sample_id:
            raise BarcodeLayoutError(
                "%s: a row in lane %s has an empty Sample_ID" % (sheet.path, lane)
            )
        if sample_id in seen:
            raise BarcodeLayoutError(
                "%s: sample %s appears more than once in lane %s"
                % (sheet.path, sample_id, lane)
            )
        seen.add(sample_id)

        index = _validate_index(row[index_column], "index", sample_id)
        if not index:
            # No index, so nothing to demultiplex this sample on. Warn and drop
            # rather than abort the lane: such a row is usually a bookkeeping gap -
            # an App-barcoded control never written into the sheet - not evidence
            # that the lane is misread.
            logger.warning(
                "%s: lane %s sample %s has no index - skipping "
                "(no barcode to demultiplex on)",
                sheet.path,
                lane_label(lane_number(lane)),
                sample_id,
            )
            continue

        index2 = (
            _validate_index(row.get(index2_column, ""), "index2", sample_id)
            if index2_column is not None
            else ""
        )

        lengths.add((len(index), len(index2)))
        entries.append(
            (sample_id, oriented_barcode(index, index2, orientation, slot_order))
        )

    if len(lengths) > 1:
        raise BarcodeLayoutError(
            "%s: lane %s mixes index lengths %s; splitBarcode needs one -b layout "
            "for the whole lane"
            % (sheet.path, lane_label(lane_number(lane)), sorted(lengths))
        )
    if not entries:
        raise SkippedLaneError(
            "%s: lane %s has no samples with barcodes - every row was skipped for "
            "an empty index" % (sheet.path, lane_label(lane_number(lane)))
        )
    return entries


def write_barcode_file(entries: Sequence[tuple[str, str]], path: str) -> str:
    """Write the headerless, tab-delimited `-B` file, and return its path.

    **Idempotent: an unchanged file is left completely alone, mtime included.** This
    matters more than it looks. redun hashes a local File as
    `hash_struct(["File", "local", path, size, mtime])` - a deliberate O(1)
    pseudo-hash, *not* the content - so rewriting identical bytes still changes the
    hash. Stage 1 regenerates these files on every launch, so an unconditional write
    would change `split_barcodes_one`'s argument hash every time, miss the cache, and
    re-run a ~25 minute splitBarcode job per lane on every rerun. That would defeat
    the rerun behaviour the pipeline depends on.
    """
    if parent := os.path.dirname(path):
        os.makedirs(parent, exist_ok=True)

    content = "".join("%s\t%s\n" % (sample_id, barcode) for sample_id, barcode in entries)

    if os.path.exists(path):
        with open(path) as f:
            if f.read() == content:
                logger.debug("%s is unchanged, leaving it alone", path)
                return path

    with open(path, "w") as f:
        _ = f.write(content)
    return path


# --------------------------------------------------------------------------
# Read files
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadFiles:
    """The per-lane fastq(s), and which one carries the barcode."""

    r1: str
    r2: str | None = None

    @property
    def is_pe(self) -> bool:
        return self.r2 is not None

    @property
    def barcode_fastq(self) -> str:
        """MGI appends the barcode to the end of the *last* read."""
        return self.r2 if self.r2 is not None else self.r1

    @property
    def paths(self) -> list[str]:
        return [self.r1] if self.r2 is None else [self.r1, self.r2]

    @property
    def cli_args(self) -> list[str]:
        """`["-1", a]` or `["-1", a, "-2", b]`."""
        if self.r2 is None:
            return ["-1", self.r1]
        return ["-1", self.r1, "-2", self.r2]


def read_files(run_dir: str, run: str, lane: int | str) -> ReadFiles:
    """Locate a lane's fastq(s).

    Layout is `{run_dir}/{LANE}/{RUN}_{LANE}_read.fq.gz` for single-end and
    `..._read_1.fq.gz` / `..._read_2.fq.gz` for paired-end.
    """
    label = lane_label(lane_number(lane))
    lane_dir = os.path.join(run_dir, label)
    single = os.path.join(lane_dir, "%s_%s_read.fq.gz" % (run, label))
    first = os.path.join(lane_dir, "%s_%s_read_1.fq.gz" % (run, label))
    second = os.path.join(lane_dir, "%s_%s_read_2.fq.gz" % (run, label))

    if os.path.exists(first) and os.path.exists(second):
        return ReadFiles(r1=first, r2=second)
    if os.path.exists(single):
        return ReadFiles(r1=single)
    if os.path.exists(first) != os.path.exists(second):
        raise BarcodeLayoutError(
            "lane %s: found only one half of the paired-end pair in %s - refusing "
            "to demultiplex an incomplete pair" % (label, lane_dir)
        )
    raise BarcodeLayoutError(
        "lane %s: no reads found. Expected one of:\n  %s\n  %s (+ _2)"
        % (label, single, first)
    )


def _iter_sequence_lines(fastq: str) -> Iterator[str]:
    """Yield every sequence line of a gzipped fastq, decompressing once.

    A generator, not a list, because `verify_layout` scans adaptively: one chunk for
    a full sheet, a few hundred thousand reads for a one-sample batch. Materialising
    the larger case, or reopening the file per chunk, would cost more than the scan.

    Callers that stop early must `close()` the generator - that is what runs the
    `with` exit and releases the decompressor.
    """
    with gzip.open(fastq, "rt") as f:
        for number, line in enumerate(f):
            if number % 4 == 1:
                yield line.rstrip("\r\n")


def _read_chunk(stream: Iterator[str], n_reads: int) -> list[str]:
    """Up to `n_reads` sequence lines from `stream`; short at end of file."""
    chunk: list[str] = []
    for line in stream:
        chunk.append(line)
        if len(chunk) >= n_reads:
            break
    return chunk


def _modal_length(lines: Iterable[str]) -> int:
    counts: dict[int, int] = {}
    for line in lines:
        counts[len(line)] = counts.get(len(line), 0) + 1
    if not counts:
        raise BarcodeLayoutError("no reads to measure")
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def read_length(fastq: str, n_reads: int = 20) -> int:
    """Modal sequence-line length of the first few reads."""
    stream = _iter_sequence_lines(fastq)
    try:
        lines = _read_chunk(stream, n_reads)
    finally:
        stream.close()
    if not lines:
        raise BarcodeLayoutError("no reads could be read from %s" % fastq)
    return _modal_length(lines)


# --------------------------------------------------------------------------
# BioInfo.csv - the run's own description of its cycle structure
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BarcodeBlock:
    """One sequenced barcode block: its machine name and its cycle count."""

    name: str
    length: int


@dataclass(frozen=True)
class BioInfo:
    """The cycle structure of one lane, as the instrument recorded it."""

    path: str
    platform: str
    read1_len: int
    read2_len: int
    blocks: list[BarcodeBlock]
    values: dict[str, str] = field(default_factory=dict)

    @property
    def is_pe(self) -> bool:
        return self.read2_len > 0

    @property
    def barcode_cycles(self) -> int:
        """Total cycles the barcode blocks occupy at the end of the read."""
        return sum(block.length for block in self.blocks)

    @property
    def declared_insert_len(self) -> int:
        """The read length the instrument claims - read 2's in PE mode.

        Used only as a cross-check: G99 overstates `Read1 Cycles` by one.
        """
        return self.read2_len if self.is_pe else self.read1_len


def _normalise_key(key: str) -> str:
    return "".join(char for char in key.lower() if char.isalnum())


def bioinfo_path(run_dir: str, lane: int | str) -> str:
    """`{run_dir}/{LANE}/BioInfo.csv`, falling back to the run root."""
    label = lane_label(lane_number(lane))
    per_lane = os.path.join(run_dir, label, "BioInfo.csv")
    if os.path.exists(per_lane):
        return per_lane
    at_root = os.path.join(run_dir, "BioInfo.csv")
    if os.path.exists(at_root):
        return at_root
    raise BioInfoError(
        "lane %s: no BioInfo.csv found. Expected one of:\n  %s\n  %s"
        % (label, per_lane, at_root)
    )


def _bioinfo_int(values: dict[str, str], field_name: str, required: bool = True) -> int:
    for alias in _BIOINFO_KEYS[field_name]:
        if values.get(alias, "") != "":
            text = values[alias]
            try:
                return int(text)
            except ValueError:
                # from None: the ValueError adds nothing the message lacks.
                raise BioInfoError(
                    "%s is not an integer: %r" % (field_name, text)
                ) from None
    if required:
        raise BioInfoError(
            "no %s field; looked for %s"
            % (field_name, list(_BIOINFO_KEYS[field_name]))
        )
    return 0


def _block_order(values: dict[str, str]) -> tuple[str, ...]:
    """Barcode block order, from `Sequence Order` when the run states it.

    G99 writes `Read1-Read2-Dualbarcode-Barcode`; T1+ writes nothing and sequences
    Barcode first. Read1/Read2 tokens are dropped - only the two barcode blocks'
    relative order matters.
    """
    raw = ""
    for alias in _BIOINFO_KEYS["sequence_order"]:
        if values.get(alias):
            raw = values[alias]
            break
    if not raw:
        return _T1_BLOCK_ORDER

    order: list[str] = []
    for token in raw.split("-"):
        name = _normalise_key(token)
        if name.startswith("read"):
            continue
        if name == "dualbarcode":
            order.append(DUAL_BARCODE)
        elif name == "barcode":
            order.append(BARCODE)
        else:
            raise BioInfoError(
                "Sequence Order %r contains an unrecognised block %r" % (raw, token)
            )
    if not order:
        raise BioInfoError("Sequence Order %r names no barcode blocks" % raw)
    return tuple(order)


def read_bioinfo(path: str) -> BioInfo:
    """Parse a lane's `BioInfo.csv` into read lengths and barcode blocks."""
    if not os.path.exists(path):
        raise BioInfoError("BioInfo.csv does not exist: %s" % path)

    values: dict[str, str] = {}
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            values[_normalise_key(row[0])] = row[1].strip() if len(row) > 1 else ""

    # Machine ID is not dependable: FT150034546 and FT150034753 are G99 runs
    # reporting a bare serial. The *schema* is reliable - only G99 writes
    # "Read1 Cycles" - and is what everything below keys off anyway, so fall back to
    # it for the label too.
    machine = values.get("machineid", "")
    if "G99" in machine.upper():
        platform = "G99"
    elif "T1" in machine.upper():
        platform = "T1+"
    elif "read1cycles" in values:
        platform = "G99"
    elif "read1len" in values:
        platform = "T1+"
    else:
        platform = machine or "unknown"

    # The primary barcode length is mandatory: without it the block list collapses
    # to [DualBarcode] and bio.blocks[0] - which every offset is measured from -
    # becomes the *dual* barcode. A single-index sheet would then anchor against the
    # wrong block's width and decode nothing, silently.
    lengths = {
        BARCODE: _bioinfo_int(values, "barcode_len"),
        DUAL_BARCODE: _bioinfo_int(values, "dual_barcode_len", required=False),
    }
    # A zero-length block was not sequenced. Dropping it here lets a single-barcode
    # run collapse to one -b without a special case.
    blocks = [
        BarcodeBlock(name=name, length=lengths[name])
        for name in _block_order(values)
        if lengths[name] > 0
    ]
    if not blocks:
        raise BioInfoError("%s: no barcode cycles declared" % path)

    return BioInfo(
        path=path,
        platform=platform,
        read1_len=_bioinfo_int(values, "read1_len"),
        read2_len=_bioinfo_int(values, "read2_len", required=False),
        blocks=blocks,
        values=values,
    )


# --------------------------------------------------------------------------
# Barcode layout - geometry from BioInfo.csv, confirmed against the reads
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BarcodeLayout:
    """Where the barcode sits: derived from BioInfo, confirmed on the reads."""

    fastq: str
    platform: str
    offset: int
    offset2: int | None
    blocks: list[BarcodeBlock]
    index_len: int
    index2_len: int
    orientation: tuple[str, str]
    hit_rate: float
    runner_up_rate: float
    n_scanned: int
    read_len: int
    declared_insert_len: int
    is_pe: bool
    slot_order: str = INDEX_FIRST
    read1_len: int | None = None
    # What the layout is accepted on; hit_rate above is derived from these and
    # reported for diagnostics only.
    hits: int = 0
    sibling_hits: int = 0
    # Coverage: which of the sheet's barcodes were actually seen. Separate from the
    # hit count, and a much deeper question - min_hits proves the layout after a few
    # dozen reads, while seeing every listed barcode takes hundreds of thousands
    # because per-sample yield has a long tail. Reported, never fatal: a barcode that
    # never appears is either a very low-yield sample or a mistyped row, and the reads
    # cannot tell those apart.
    n_expected: int = 0
    unobserved: frozenset[str] = frozenset()
    coverage_scanned: int = 0
    coverage_exhausted: bool = False
    # Filled only when coverage is bad enough to suggest the sheet is systematically
    # wrong: the sheet rewrite that would explain it, in the same words a refusal uses.
    coverage_diagnosis: str = ""

    @property
    def coverage_complete(self) -> bool:
        """True when every barcode the sheet lists was seen in the reads."""
        return self.n_expected > 0 and not self.unobserved

    @property
    def slot_lengths(self) -> tuple[int, int]:
        """`(slot 1, slot 2)` index lengths, in the order the machine read them."""
        return _slot_lengths(self.index_len, self.index2_len, self.slot_order)

    @property
    def anchor_disagrees(self) -> bool:
        """True when BioInfo's declared read length is not the real one.

        Reported, not fatal - the read length is the authority for the anchor.
        """
        return self.offset != self.declared_insert_len

    @property
    def anchor_is_g99_fencepost(self) -> bool:
        """True for G99's systematic one-cycle overstatement.

        G99 declares `Read1 Cycles,101` for a 100-cycle read 1 and `151` for a
        150-cycle one, while the same file's `Sequence Type` (`SE100+8+10`) gives
        the true figure - it counts the boundary, not the length. Confirmed on
        FT150034703, FT150034546 and FT150034753; T1+ never does it. Distinguished
        from a genuine mismatch so a routine G99 run does not log something that
        reads like a corrupt file.
        """
        return self.declared_insert_len - self.offset == 1

    def describe(self) -> str:
        blocks = " + ".join("%s %d" % (b.name, b.length) for b in self.blocks)
        slot1, slot2 = self.slot_lengths
        first, second = (
            ("index2", "index") if self.slot_order == INDEX2_FIRST else ("index", "index2")
        )
        mode = "PE (read 2)" if self.is_pe else "SE"
        text = "%s %s: read %d bp = insert %d + [%s]; %s %d @ %d" % (
            self.platform,
            mode,
            self.read_len,
            self.offset,
            blocks,
            first,
            slot1,
            self.offset,
        )
        if slot2:
            text += ", %s %d @ %s" % (second, slot2, self.offset2)
        text += "; orientation index=%s index2=%s; slot order %s" % (
            self.orientation[0],
            self.orientation[1],
            self.slot_order,
        )
        # Absolute hits first - that is what the layout was accepted on. The rate
        # follows as context: it is the sheet's share of the lane, the number to
        # check when a batch's undecoded share is surprising.
        text += "; %d hits (sibling strand %d) over %d reads; hit-rate %.3f (sibling strand %.3f)" % (
            self.hits,
            self.sibling_hits,
            self.n_scanned,
            self.hit_rate,
            self.runner_up_rate,
        )
        if self.anchor_is_g99_fencepost:
            text += (
                "\n  note: BioInfo.csv declares %d cycles of insert against %d "
                "measured - the usual G99 one-cycle overstatement; using the reads."
                % (self.declared_insert_len, self.offset)
            )
        elif self.anchor_disagrees:
            text += (
                "\n  WARNING: BioInfo.csv declares %d cycles of insert but the reads "
                "give %d - that is not the known G99 off-by-one; check the run before "
                "trusting this lane." % (self.declared_insert_len, self.offset)
            )
        return text


def barcode_geometry(
    bio: BioInfo, read_len: int, index_len: int, index2_len: int
) -> tuple[int, int | None]:
    """`(offset, offset2)` for one lane, in barcode-fastq coordinates.

    The barcode blocks sit at the **end** of the read, so the anchor is
    `read_len - total barcode cycles`, not BioInfo's declared read length - G99
    overstates that by one cycle and anchoring on it sends the whole lane to
    `undecoded`.

    `index2` starts at `offset + len(block 1)`, **not** `offset + len(index)`: a
    block can be longer than the index the sheet puts in it (T1+ can sequence 10
    cycles for an 8-base index), and those unused cycles sit between the two indices.
    """
    cycles = bio.barcode_cycles
    if read_len <= cycles:
        raise BarcodeLayoutError(
            "reads are %d bp but %s declares %d barcode cycles - there is no insert left"
            % (read_len, bio.path, cycles)
        )

    offset = read_len - cycles
    first_block = bio.blocks[0]
    if index_len > first_block.length:
        raise BarcodeLayoutError(
            "the sheet's index is %d bases but %s sequenced only %d cycles for the "
            "first barcode block (%s)"
            % (index_len, bio.path, first_block.length, first_block.name)
        )

    if not index2_len:
        return offset, None

    if len(bio.blocks) < 2:
        raise BarcodeLayoutError(
            "the sheet has a dual index but %s declares only one barcode block "
            "(%s %d cycles)" % (bio.path, first_block.name, first_block.length)
        )
    second_block = bio.blocks[1]
    if index2_len > second_block.length:
        raise BarcodeLayoutError(
            "the sheet's index2 is %d bases but %s sequenced only %d cycles for the "
            "second barcode block (%s)"
            % (index2_len, bio.path, second_block.length, second_block.name)
        )
    return offset, offset + first_block.length


def _barcode_slice(
    line: str, offset: int, offset2: int | None, slot1_len: int, slot2_len: int
) -> str:
    """The barcode a read carries at the given offsets, slot 1 then slot 2.

    A block can be wider than the index it holds, so slot 2 is taken from its own
    offset rather than from the end of slot 1 - the unused cycles in between are never
    read.
    """
    observed = line[offset : offset + slot1_len]
    if offset2 is not None:
        observed += line[offset2 : offset2 + slot2_len]
    return observed


def _count_hits(
    usable: Sequence[str],
    offset: int,
    offset2: int | None,
    slot1_len: int,
    slot2_len: int,
    expected: set[str],
    seen: set[str] | None = None,
) -> int:
    """How many scanned reads carry a **complete sheet pair** at the offsets.

    A complete pair, not two indices matched independently: the two halves must come
    from the *same* sample, so a read whose slot 1 belongs to one sample and slot 2
    to another is not a hit.

    `seen`, when given, collects *which* listed barcodes were matched. That is a set of
    at most one entry per sheet row, so it rides along with the hit count instead of
    costing a second pass - which is what makes the coverage check in `verify_layout`
    affordable.
    """
    hits = 0
    for line in usable:
        observed = _barcode_slice(line, offset, offset2, slot1_len, slot2_len)
        if observed in expected:
            hits += 1
            if seen is not None:
                seen.add(observed)
    return hits


# --------------------------------------------------------------------------
# Failure diagnostics - what the reads say, in the sheet's own terms
# --------------------------------------------------------------------------

# Sheet-level explanations for a lane whose reads do not carry the sheet's barcodes.
# Each entry rewrites the sheet's (index, index2) pairs and scores the rewrite against
# the same reads with the run's derived layout held FIXED - so this answers "how is the
# sheet wrong", separately from the reverse-strand sibling's "the run is not what
# BioInfo.csv says".
#
# Ordered commonest first: the i5 column alone is the usual culprit, because the two
# Illumina i5 workflow conventions differ in exactly that column and nothing else.
_SHEET_TRANSFORMS = (
    (
        "index2 (i5) column is reverse-complemented",
        "reverse-complement the index2 column, or re-export the sheet in the other "
        "Illumina i5 workflow convention",
        lambda index, index2: (index, revcomp(index2)),
    ),
    (
        "index (i7) column is reverse-complemented",
        "reverse-complement the index column",
        lambda index, index2: (revcomp(index), index2),
    ),
    (
        "both index columns are reverse-complemented",
        "reverse-complement both index columns",
        lambda index, index2: (revcomp(index), revcomp(index2)),
    ),
    (
        "index and index2 columns are swapped",
        "swap the index and index2 columns",
        lambda index, index2: (index2, index),
    ),
    (
        "columns are swapped and both reverse-complemented",
        "swap the index and index2 columns and reverse-complement both",
        lambda index, index2: (revcomp(index2), revcomp(index)),
    ),
)


def _transform_scores(
    pairs: Sequence[tuple[str, str]],
    sample_reads: Sequence[str],
    bio: BioInfo,
    read_len: int,
    orientation: tuple[str, str],
    slot_order: str,
    sibling_expected: set[str] | None,
) -> list[tuple[str, str, int | None, str]]:
    """Score every sheet rewrite: `[(label, fix, hits or None, note), ...]`.

    `hits is None` means the rewrite could not be *tested* on this lane - its slot
    widths do not fit the sequenced blocks, so it has no offsets. That is reported as
    such rather than as a zero, otherwise "nothing matched" would be claiming more than
    was actually checked. It is the same limitation the reverse-strand sibling has on
    asymmetric blocks.
    """
    results: list[tuple[str, str, int | None, str]] = []
    original = list(pairs)

    for label, fix, transform in _SHEET_TRANSFORMS:
        rewritten = [transform(index, index2) for index, index2 in original]
        # A rewrite that empties a column is a swap on a single-index lane: there is no
        # second column to swap with, so it is not a candidate explanation at all.
        if any(not index for index, _ in rewritten):
            continue
        if rewritten == original:
            continue
        lengths = {(len(index), len(index2)) for index, index2 in rewritten}
        if len(lengths) > 1:
            continue
        index_len, index2_len = lengths.pop()
        slot1_len, slot2_len = _slot_lengths(index_len, index2_len, slot_order)
        try:
            offset, offset2 = barcode_geometry(bio, read_len, slot1_len, slot2_len)
        except BarcodeLayoutError:
            results.append((label, fix, None, ""))
            continue
        expected = {
            oriented_barcode(index, index2, orientation, slot_order)
            for index, index2 in rewritten
        }
        # Some rewrites are algebraically the same set as the opposite-strand reading -
        # for a single-index lane, "index reverse-complemented" IS the sibling. Say so
        # in the same breath rather than letting the two reports contradict each other.
        note = (
            "equivalent to the reverse-strand reading"
            if sibling_expected is not None and expected == sibling_expected
            else ""
        )
        results.append(
            (
                label,
                fix,
                _count_hits(
                    sample_reads, offset, offset2, slot1_len, slot2_len, expected
                ),
                note,
            )
        )

    results.sort(key=lambda row: (row[2] is None, -(row[2] or 0)))
    return results


def _census(
    sample_reads: Sequence[str],
    offset: int,
    offset2: int | None,
    slot1_len: int,
    slot2_len: int,
) -> tuple[collections.Counter, int]:
    """`(counts of the barcodes actually present, polyG/N read count)`."""
    counts: collections.Counter = collections.Counter()
    n_nosignal = 0
    width = slot1_len + slot2_len

    for line in sample_reads:
        observed = _barcode_slice(line, offset, offset2, slot1_len, slot2_len)
        if len(observed) < width:
            continue
        if set(observed) - _VALID_BASES:
            # str.translate passes unknown characters straight through, so a junk slot
            # would come out of sheet_indices as plausible-looking nonsense instead of
            # being visibly junk.
            continue
        if observed == "G" * width or observed == "N" * width:
            # MGI writes polyG (polyN on some recipes) where there was no signal. Folded
            # into one figure so it cannot crowd the table - but ONLY polyG/polyN. A
            # lane really carrying polyA or polyT is carrying signal, and folding that
            # away would report "nothing observed" when there plainly is something.
            n_nosignal += 1
            continue
        counts[observed] += 1

    return counts, n_nosignal


def _mismatch_report(
    bio: BioInfo,
    pairs: Sequence[tuple[str, str]],
    sample_reads: Sequence[str],
    layout: "BarcodeLayout",
    sibling_expected: set[str] | None,
    sample_ids: dict[tuple[str, str], str] | None,
    min_hits: int,
) -> str:
    """The actionable half of a refusal: what would have matched, and what is there.

    Deliberately NOT part of `BarcodeLayout.describe()`, which also runs on the success
    path - a healthy lane has no business logging a census.
    """
    slot1_len, slot2_len = layout.slot_lengths
    lines: list[str] = [""]

    scores = _transform_scores(
        pairs,
        sample_reads,
        bio,
        layout.read_len,
        layout.orientation,
        layout.slot_order,
        sibling_expected,
    )
    matched = [row for row in scores if row[2] is not None and row[2] >= min_hits]

    if matched:
        label, fix, hits, note = matched[0]
        lines.append("  DIAGNOSIS: the sample sheet's %s." % label)
        lines.append(
            "    rewritten that way, %d of the %d sampled reads match this sheet."
            % (hits, len(sample_reads))
        )
        lines.append("    FIX: %s." % fix)
        if note:
            lines.append("    (%s)" % note)
    else:
        lines.append(
            "  DIAGNOSIS: no complement or column-order rewrite of this sheet matches "
            "the reads either,"
        )
        lines.append(
            "    so the listed barcodes are themselves wrong, or this is the wrong "
            "sheet for this run."
        )

    if tested := ", ".join(
        "%s (%d)" % (label, hits) for label, _, hits, _ in scores if hits is not None
    ):
        lines.append("    rewrites tested: %s" % tested)
    if untestable := ", ".join(
        label for label, _, hits, _ in scores if hits is None
    ):
        lines.append("    not testable on this lane's block widths: %s" % untestable)

    counts, n_nosignal = _census(
        sample_reads, layout.offset, layout.offset2, slot1_len, slot2_len
    )
    total = sum(counts.values()) + n_nosignal

    lines.append("")
    lines.append("  OBSERVED BARCODES, as they should appear in the sample sheet:")
    if not counts:
        lines.append(
            "    nothing usable observed in %d sampled reads (%d were polyG/N "
            "no-signal)" % (len(sample_reads), n_nosignal)
        )
        return "\n".join(lines)

    lines.append(
        "    top %d of %d distinct, over %d sampled reads; %.1f%% polyG/N no-signal"
        % (
            min(CENSUS_TOP_N, len(counts)),
            len(counts),
            len(sample_reads),
            100.0 * n_nosignal / total if total else 0.0,
        )
    )
    lines.append(
        "       count   share  %-*s %-*s  sheet row"
        % (max(slot1_len, 5), "index", max(slot2_len, 6), "index2")
    )
    listed = set(pairs)
    for observed, count in counts.most_common(CENSUS_TOP_N):
        index, index2 = sheet_indices(
            observed,
            layout.orientation,
            layout.slot_order,
            layout.index_len,
            layout.index2_len,
        )
        pair = (index, index2)
        # `sample_ids` comes from the sheet being complained about, so when that sheet
        # is systematically wrong every row here reads "not in sheet" - correctly: none
        # of the barcodes actually present is listed in it. The naming earns its keep on
        # a partly-wrong sheet, where it separates the mistyped rows from the good ones.
        if sample_ids is not None:
            who = sample_ids.get(pair, "** not in sheet **")
        elif pair in listed:
            who = "listed in this sheet"
        else:
            who = "** not in sheet **"
        lines.append(
            "    %8d  %5.2f%%  %-*s %-*s  %s"
            % (
                count,
                100.0 * count / total if total else 0.0,
                max(slot1_len, 5),
                index,
                max(slot2_len, 6),
                index2 or "-",
                who,
            )
        )
    return "\n".join(lines)


def verify_layout(
    fastq: str,
    bio: BioInfo,
    pairs: Sequence[tuple[str, str]],
    orientation: tuple[str, str],
    slot_order: str,
    min_hits: int = DEFAULT_MIN_HITS,
    max_scan_reads: int = DEFAULT_MAX_SCAN_READS,
    coverage_max_scan_reads: int = COVERAGE_MAX_SCAN_READS,
    sample_ids: dict[tuple[str, str], str] | None = None,
) -> BarcodeLayout:
    """Confirm a *derived* `(orientation, slot_order)` against the reads.

    `derive_layout` fixes orientation and slot order from SE-vs-PE, so this verifies
    rather than searches. Only the reads can catch a mismatched sheet/run pair, wrong
    geometry, or an MGI-native run mislabelled as Illumina-converted.

    The scan is **adaptive**, in two phases. First it reads chunks until the derived
    layout reaches `min_hits`, or gives up at `max_scan_reads`; evidence is an absolute
    count, so a small batch is not penalised, it just reads further. Once the layout is
    proven it keeps going - much more cheaply, since nothing can fail from here - until
    every listed barcode has been seen or `coverage_max_scan_reads` is reached, which is
    what lets an unobserved sheet row be reported at all.

    `sample_ids` maps `(index, index2)` to a sample name, and is used only to label the
    census in a failure report. It is optional so this stays callable with nothing but
    a sheet's index pairs.

    Two candidates are scored over the **same** reads at fixed offsets: the
    **derived** layout and its **reverse-strand sibling**. Either aborts:

    1. the sibling clears `min_hits` *and* out-scores the derived layout - the reads
       match the *opposite* strand, so SE/PE is likely mislabelled in `BioInfo.csv`,
       or the library is MGI-native;
    2. the derived layout is short of `min_hits` at the cap - sheet and run are not a
       matching pair, the geometry is wrong, or the library is not
       Illumina-converted.
    """
    if not pairs:
        raise BarcodeLayoutError("no indices supplied to check %s" % fastq)
    if slot_order not in SLOT_ORDERS:
        raise BarcodeLayoutError(
            "slot_order must be one of %s, got %r" % (list(SLOT_ORDERS), slot_order)
        )

    lengths = {(len(index), len(index2)) for index, index2 in pairs}
    if len(lengths) > 1:
        raise BarcodeLayoutError(
            "lane mixes index lengths %s; splitBarcode needs one -b layout for the "
            "whole lane.\n  fastq: %s" % (sorted(lengths), fastq)
        )
    index_len, index2_len = lengths.pop()

    sibling = next(
        candidate
        for candidate in _COHERENT_LAYOUTS
        if candidate != (orientation, slot_order)
    )

    stream = _iter_sequence_lines(fastq)
    try:
        chunk = _read_chunk(stream, SCAN_CHUNK_READS)
        if not chunk:
            raise BarcodeLayoutError("no reads could be read from %s" % fastq)

        # Modal read length only: a handful of trimmed or truncated reads must not
        # move the anchor for everything else. Fixed from the first chunk and every
        # later chunk filtered to it, so a truncated read a hundred thousand reads in
        # cannot move an already-derived anchor.
        read_len = _modal_length(chunk)

        def resolve(
            candidate_orientation: tuple[str, str], candidate_order: str, strict: bool
        ):
            """`(offset, offset2, slot lengths, expected barcodes)` - or None.

            Resolved once before the scan: it depends only on the geometry and the
            sheet. Only the counting is per chunk.
            """
            slot1_len, slot2_len = _slot_lengths(index_len, index2_len, candidate_order)
            try:
                offset, offset2 = barcode_geometry(bio, read_len, slot1_len, slot2_len)
            except BarcodeLayoutError:
                # The derived layout must fit the sequenced blocks; not fitting is a
                # real fail-loud error. The sibling may legitimately not fit
                # (asymmetric block lengths make its offsets impossible), which just
                # scores it zero - it cannot be the answer either way.
                if strict:
                    raise
                return None
            expected = {
                oriented_barcode(index, index2, candidate_orientation, candidate_order)
                for index, index2 in pairs
            }
            return offset, offset2, slot1_len, slot2_len, expected

        offset, offset2, slot1_len, slot2_len, expected = resolve(
            orientation, slot_order, strict=True
        )
        sibling_plan = resolve(sibling[0], sibling[1], strict=False)

        hits = 0
        sibling_hits = 0
        n_scanned = 0
        n_read = 0
        n_expected = len(expected)
        seen: set[str] = set()
        sample_reads: list[str] = []
        while True:
            n_read += len(chunk)
            # Both candidates counted over the SAME reads, so the sibling comparison
            # stays like-for-like at every chunk boundary.
            usable = [line for line in chunk if len(line) == read_len]
            n_scanned += len(usable)
            # A bounded sample kept aside so a refusal can report what the reads
            # actually carry, and score sheet rewrites, without a second pass.
            if len(sample_reads) < DIAGNOSTIC_SAMPLE_READS:
                sample_reads.extend(
                    usable[: DIAGNOSTIC_SAMPLE_READS - len(sample_reads)]
                )
            hits += _count_hits(
                usable, offset, offset2, slot1_len, slot2_len, expected, seen
            )
            if sibling_plan is not None:
                sibling_hits += _count_hits(usable, *sibling_plan)

            if hits < min_hits:
                # Still proving the layout. Stop at the failure cap: a mismatched
                # sheet/run pair accumulates hits at chance and will never get there.
                if n_read >= max_scan_reads:
                    break
            elif len(seen) >= n_expected or n_read >= coverage_max_scan_reads:
                # Layout proven; the only question left is coverage, and it is answered
                # either way. Nothing below can now fail, so this is the normal exit.
                break
            chunk = _read_chunk(stream, SCAN_CHUNK_READS)
            if not chunk:
                break  # end of file: all the evidence this lane has to offer
    finally:
        # Closing exits the generator's `with` and releases the decompressor. On a
        # healthy run this abandons the stream after the first chunk.
        stream.close()

    layout = BarcodeLayout(
        fastq=fastq,
        platform=bio.platform,
        offset=offset,
        offset2=offset2,
        blocks=list(bio.blocks),
        index_len=index_len,
        index2_len=index2_len,
        orientation=orientation,
        slot_order=slot_order,
        hit_rate=hits / float(n_scanned) if n_scanned else 0.0,
        runner_up_rate=sibling_hits / float(n_scanned) if n_scanned else 0.0,
        n_scanned=n_scanned,
        read_len=read_len,
        declared_insert_len=bio.declared_insert_len,
        is_pe=bio.is_pe,
        hits=hits,
        sibling_hits=sibling_hits,
        n_expected=n_expected,
        unobserved=frozenset(expected - seen),
        coverage_scanned=n_read,
        coverage_exhausted=n_read >= coverage_max_scan_reads,
    )

    sibling_expected = sibling_plan[4] if sibling_plan is not None else None

    # The coherence tripwire, checked before the generic low-evidence gate so a clear
    # opposite-strand match gets a specific diagnosis, not "not enough hits". Guarded
    # two ways: strict >, so a tie falls through to the empty-index refusal instead
    # of being mislabelled opposite-strand; and the sibling must itself clear
    # min_hits, so a mismatched sheet/run pair (both near zero, noise deciding the
    # winner) reads as low evidence.
    #
    # Absolute hits on both clauses, like the gate below: an opposite-strand
    # 8-sample batch has a sibling *rate* near 0.0015, so a rate-based clause would
    # stop firing for exactly the small batches this supports.
    if sibling_hits >= min_hits and sibling_hits > hits:
        raise BarcodeLayoutError(
            "the reads match the opposite strand in %s.\n  %s\n  the reverse-strand "
            "sibling (%s/%s, %s) scores %d against the derived layout's %d - wrong "
            "library convention? (SE/PE mislabelled in BioInfo.csv, or an MGI-native "
            "library)%s"
            % (
                fastq,
                layout.describe(),
                sibling[0][0],
                sibling[0][1],
                sibling[1],
                sibling_hits,
                hits,
                _mismatch_report(
                    bio, pairs, sample_reads, layout, sibling_expected,
                    sample_ids, min_hits,
                ),
            )
        )

    if hits < min_hits:
        raise BarcodeLayoutError(
            "the sheet's indices are not where %s says they are.\n  %s\n"
            "  only %d of %d comparable reads carried a barcode this sheet lists at "
            "those offsets, against the %d needed (%d reads consumed; the rest were "
            "off the modal length and not comparable). The derived layout assumes an "
            "Illumina-converted library (SE -> i7+i5 forward, PE -> rc(i5)+rc(i7)); "
            "too few hits usually means an MGI-native library, the wrong sheet/run "
            "pair, or wrong geometry.\n"
            "  Batch size is NOT a cause - evidence is counted absolutely, so a sheet "
            "of one sample passes as readily as a full one. The exception is a batch "
            "whose samples are so low-yield that %d of their reads do not appear "
            "within the %d-read cap.\n  fastq: %s%s"
            % (
                bio.path,
                layout.describe(),
                hits,
                n_scanned,
                min_hits,
                n_read,
                min_hits,
                max_scan_reads,
                fastq,
                _mismatch_report(
                    bio, pairs, sample_reads, layout, sibling_expected,
                    sample_ids, min_hits,
                ),
            )
        )

    # A lane can clear min_hits on a sheet that is systematically wrong. Measured on
    # FT150034703 L01 (3788 rows): reverse-complementing the whole i7 column still
    # scores 8637 hits, because 34 of the rewritten barcodes collide with real ones and
    # those few samples' reads pile up - so the hit gate passes and ~99% of the lane
    # would go to `undecoded`. Coverage is what catches it: only 244 of 3788 listed
    # barcodes were ever seen. When that much of the sheet is missing, run the same
    # rewrite panel a refusal would, so the warning can name the cause instead of just
    # counting the symptom.
    if layout.n_expected and len(layout.unobserved) > layout.n_expected // 2:
        best = next(
            (
                row
                for row in _transform_scores(
                    pairs, sample_reads, bio, read_len, orientation, slot_order,
                    sibling_expected,
                )
                if row[2] is not None and row[2] >= min_hits and row[2] > hits
            ),
            None,
        )
        if best is not None:
            layout = replace(
                layout,
                coverage_diagnosis="the sample sheet's %s (that rewrite scores %d "
                "against this sheet's %d) - FIX: %s"
                % (best[0], best[2], hits, best[1]),
            )

    return layout


def barcode_params(
    layout: BarcodeLayout,
    mismatch: int = 1,
    pe_offset_base: str = PE_OFFSET_CONCATENATED,
) -> list[tuple[int, int, int]]:
    """`[(start, length, mismatch), ...]` - one tuple per `-b`.

    Each `-b` takes only the bases the sheet uses, so a block with unused trailing
    cycles (T1+ sequences 10, the sheet supplies 8) yields `-b <start> 8 <mismatch>`
    and the junk cycles are never read.

    PE geometry is in *read 2* coordinates. `pe_offset_base` selects whether
    splitBarcode counts `-b` that way or across the concatenated read, so the
    experiment flips a config value rather than editing this function.
    """
    if pe_offset_base not in PE_OFFSET_BASES:
        raise ValueError(
            "pe_offset_base must be one of %s, got %r"
            % (list(PE_OFFSET_BASES), pe_offset_base)
        )

    shift = 0
    if layout.is_pe and pe_offset_base == PE_OFFSET_CONCATENATED:
        if layout.read1_len is None:
            raise BarcodeLayoutError(
                "pe_offset_base=concatenated needs read 1's length, which was not measured"
            )
        shift = layout.read1_len

    slot1_len, slot2_len = layout.slot_lengths
    params = [(layout.offset + shift, slot1_len, mismatch)]
    if slot2_len:
        assert layout.offset2 is not None
        params.append((layout.offset2 + shift, slot2_len, mismatch))
    return params


def format_b_args(params: Sequence[tuple[int, int, int]]) -> str:
    """`-b 100 10 1 -b 110 8 1`."""
    return " ".join(
        "-b %d %d %d" % (start, length, mismatch) for start, length, mismatch in params
    )


def b_args(params: Sequence[tuple[int, int, int]]) -> list[str]:
    """The same, as argv tokens for a Job1Spec."""
    return [
        token
        for start, length, mismatch in params
        for token in ("-b", str(start), str(length), str(mismatch))
    ]


# --------------------------------------------------------------------------
# Per-lane plan
# --------------------------------------------------------------------------


# How many unobserved rows to name before the list is truncated. A lane where hundreds
# are missing has one systematic problem, not hundreds of separate ones, so the list is
# there to identify the problem, not to enumerate it.
UNOBSERVED_REPORT_LIMIT = 20


def _log_coverage(
    label: str, layout: BarcodeLayout, sample_ids: dict[tuple[str, str], str]
) -> None:
    """Report which listed barcodes never turned up in the reads.

    Deliberately a warning and not a refusal. The reads cannot distinguish a mistyped
    row from a genuinely low-yield sample - measured on FT150034703 L01, a healthy lane
    still has 172 of 3788 barcodes unseen at 5x coverage and 8 unseen at 40x - so this
    states the scan depth and lets the operator judge, rather than aborting a good run.
    """
    if not layout.n_expected:
        return

    if layout.coverage_complete:
        logger.info(
            "lane %s: all %d listed barcodes observed within %d reads",
            label,
            layout.n_expected,
            layout.coverage_scanned,
        )
        return

    missing = sorted(
        sheet_indices(
            barcode,
            layout.orientation,
            layout.slot_order,
            layout.index_len,
            layout.index2_len,
        )
        for barcode in layout.unobserved
    )
    shown = ", ".join(
        "%s (%s%s)" % (sample_ids.get(pair, "?"), pair[0], "+" + pair[1] if pair[1] else "")
        for pair in missing[:UNOBSERVED_REPORT_LIMIT]
    )
    if len(missing) > UNOBSERVED_REPORT_LIMIT:
        shown += ", and %d more" % (len(missing) - UNOBSERVED_REPORT_LIMIT)

    if layout.coverage_diagnosis:
        # Checked FIRST, and deliberately before the shallow-scan branch: a sheet that
        # is systematically wrong always runs the coverage scan to its cap, so ordering
        # this second would let "too shallow to judge" swallow the actual finding.
        # Verified on FT150034703 L01 with the i7 column reverse-complemented, where
        # 3544 of 3788 barcodes go unseen and the cap is always reached.
        logger.warning(
            "lane %s: only %d of %d listed barcodes were seen in %d reads. This looks "
            "like %s. Launching as-is would send most of the lane to `undecoded`. "
            "Unseen: %s",
            label,
            layout.n_expected - len(missing),
            layout.n_expected,
            layout.coverage_scanned,
            layout.coverage_diagnosis,
            shown,
        )
        return

    if layout.coverage_exhausted:
        # The cap bound before every barcode was seen, so absence here is not evidence
        # of anything. Say that rather than letting the list read as an accusation.
        logger.warning(
            "lane %s: %d of %d listed barcodes were not seen in the first %d reads, "
            "where the coverage scan stopped - too shallow to judge, so these may "
            "simply be the lane's lowest-yield samples: %s",
            label,
            len(missing),
            layout.n_expected,
            layout.coverage_scanned,
            shown,
        )
        return

    logger.warning(
        "lane %s: %d of %d listed barcodes never appeared in %d reads - either the "
        "lane's lowest-yield samples, or rows whose barcodes are wrong: %s",
        label,
        len(missing),
        layout.n_expected,
        layout.coverage_scanned,
        shown,
    )


@dataclass(frozen=True)
class LanePlan:
    """Everything the demultiplex job needs for one lane, resolved up front.

    Resolved in the composing redun task rather than inside a Job1Spec, following
    mgi_prism's parse-time resolution: a mismatched sheet/run pair then aborts before
    any Slurm job is submitted.
    """

    lane: str
    entries: list[tuple[str, str]]
    reads: ReadFiles
    bio: BioInfo
    layout: BarcodeLayout
    params: list[tuple[int, int, int]]
    pe_offset_base: str

    @property
    def b_args(self) -> list[str]:
        return b_args(self.params)


def lane_plan(
    sheet: MgiSampleSheet,
    lane: int | str,
    run_dir: str,
    run: str,
    mismatch: int = 1,
    pe_offset_base: str = PE_OFFSET_CONCATENATED,
    min_hits: int = DEFAULT_MIN_HITS,
    max_scan_reads: int = DEFAULT_MAX_SCAN_READS,
    library_type: str = LIBRARY_TYPE_ILLUMINA,
) -> LanePlan:
    """Resolve one lane end to end: reads, BioInfo geometry, orientation, `-b`.

    Per lane, deliberately: two lanes of one run can carry different index lengths,
    so the lengths that decide each `-b`'s width are resolved from that lane's rows
    against that lane's `BioInfo.csv`.
    """
    label = lane_label(lane_number(lane))
    reads = read_files(run_dir, run, label)
    bio = read_bioinfo(bioinfo_path(run_dir, label))

    if bio.is_pe != reads.is_pe:
        raise BarcodeLayoutError(
            "lane %s: %s declares %s but the run directory holds %s fastq(s)"
            % (
                label,
                bio.path,
                "paired-end" if bio.is_pe else "single-end",
                "a paired-end pair of" if reads.is_pe else "a single",
            )
        )

    # Derived from SE-vs-PE for an Illumina-converted library, not searched for;
    # verify_layout then confirms the choice against the reads. bio.is_pe is the
    # derivation's only input, and the check above guards it against a run directory
    # that disagrees with BioInfo.csv.
    orientation, slot_order = derive_layout(bio.is_pe, library_type)
    sample_ids = sample_ids_by_index(sheet, label)
    layout = verify_layout(
        reads.barcode_fastq,
        bio,
        index_pairs(sheet, label),
        orientation,
        slot_order,
        min_hits=min_hits,
        max_scan_reads=max_scan_reads,
        sample_ids=sample_ids,
    )
    if reads.is_pe:
        layout = replace(layout, read1_len=read_length(reads.r1))

    logger.info("lane %s: %s", label, layout.describe())
    _log_coverage(label, layout, sample_ids)

    return LanePlan(
        lane=label,
        entries=barcode_entries(
            sheet, label, orientation=layout.orientation, slot_order=layout.slot_order
        ),
        reads=reads,
        bio=bio,
        layout=layout,
        params=barcode_params(layout, mismatch, pe_offset_base),
        pe_offset_base=pe_offset_base,
    )
