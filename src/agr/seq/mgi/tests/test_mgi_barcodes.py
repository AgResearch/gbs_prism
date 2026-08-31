"""Tests for MGI barcode geometry and layout verification.

Stdlib-only, so these run under `nix run '.#tests'`.

A wrong offset produces a run that *looks* successful while sending ~100% of reads
to `undecoded`, so these pin the arithmetic against both real BioInfo.csv fixtures
(T1+ and G99, which order their barcode blocks oppositely) and against synthesised
reads.
"""

import gzip
import logging
import os
import os.path

import pytest

from agr.seq.mgi.barcodes import (
    BARCODE,
    DUAL_BARCODE,
    FORWARD,
    INDEX2_FIRST,
    INDEX_FIRST,
    LIBRARY_TYPE_MGI,
    REVCOMP,
    BarcodeLayoutError,
    BioInfoError,
    _COHERENT_LAYOUTS,
    _log_coverage,
    _sheet_columns,
    barcode_geometry,
    barcode_params,
    derive_layout,
    format_b_args,
    oriented_barcode,
    read_bioinfo,
    lane_plan,
    revcomp,
    sample_ids_by_index,
    sheet_indices,
    write_barcode_file,
    verify_layout,
)
from agr.seq.mgi.sample_sheet import (
    index_pairs,
    read_sample_sheet,
    samples_for_lane,
)

HERE = os.path.dirname(__file__)
T1PLUS_BIOINFO = os.path.join(HERE, "BioInfo-T1plus-SE.csv")
G99_BIOINFO = os.path.join(HERE, "BioInfo-G99-SE.csv")

# The reference run's first library, DL100018469 / SQ5420.
INDEX = "CTAGTGCTCT"  # i7, 10 bases
INDEX2 = "CCAACAGA"  # i5, 8 bases
READ_LEN = 118  # 100 bp insert + 10 + 8 barcode cycles


def test_t1plus_bioinfo_sequences_barcode_before_dual_barcode():
    bio = read_bioinfo(T1PLUS_BIOINFO)
    assert bio.platform == "T1+"
    assert bio.read1_len == 100
    assert bio.read2_len == 0
    assert not bio.is_pe
    assert [(b.name, b.length) for b in bio.blocks] == [(BARCODE, 10), (DUAL_BARCODE, 8)]
    assert bio.barcode_cycles == 18


def test_g99_bioinfo_reverses_the_block_order():
    """G99 states `Sequence Order,Read1-Read2-Dualbarcode-Barcode`; T1+ leaves it implicit.

    The sheet's `index` is always the *first* block on the machine, so the block
    order - not the key names - is what decides which -b gets which width.
    """
    bio = read_bioinfo(G99_BIOINFO)
    assert bio.platform == "G99"
    assert [(b.name, b.length) for b in bio.blocks] == [(DUAL_BARCODE, 8), (BARCODE, 10)]
    assert bio.barcode_cycles == 18


def test_t1plus_geometry_matches_hand_made_ground_truth():
    """DL100018479 (same layout as the reference run) -> -b 100 10 1 -b 110 8 1."""
    bio = read_bioinfo(T1PLUS_BIOINFO)
    assert barcode_geometry(bio, READ_LEN, len(INDEX), len(INDEX2)) == (100, 110)


def test_g99_geometry_matches_hand_made_ground_truth():
    """FT150034703 -> -b 100 8 1 -b 108 10 1: same anchor, blocks the other way round."""
    bio = read_bioinfo(G99_BIOINFO)
    assert barcode_geometry(bio, READ_LEN, 8, 10) == (100, 108)


def test_the_anchor_comes_from_the_reads_not_the_declared_read_length():
    """G99 overstates `Read1 Cycles` by exactly one (101 for a 100-cycle read).

    Anchoring on the declared value would put every -b one cycle out and send the
    whole lane to `undecoded`.
    """
    bio = read_bioinfo(G99_BIOINFO)
    assert bio.declared_insert_len == 101  # what the file claims
    offset, _ = barcode_geometry(bio, READ_LEN, 8, 10)
    assert offset == 100  # what the reads say: 118 - 18


def test_index2_offset_uses_the_block_length_not_the_index_length(tmp_path):
    """A block can be longer than the index the sheet puts in it.

    Those unused cycles sit *between* the two indices, so index2 starts at
    `offset + len(block 1)`. Using `offset + len(index)` would read index2 two
    cycles early. The reference run cannot show this - its blocks and indices are
    the same size - so the geometry is exercised against a block that is wider.
    """
    bioinfo = tmp_path / "BioInfo.csv"
    _ = bioinfo.write_text(
        "Machine ID,INV-MGI-T1\nRead1Len,100\nRead2Len,0\nBarcodeLen,12\nDualBarcodeLen,8\n"
    )
    bio = read_bioinfo(str(bioinfo))

    # 8-base index in a 12-cycle block, 8-base index2 in an 8-cycle block.
    offset, offset2 = barcode_geometry(bio, 120, 8, 8)
    assert offset == 100  # 120 - (12 + 8)
    assert offset2 == 112  # 100 + 12, NOT 100 + 8


def test_geometry_refuses_an_index_wider_than_its_block():
    bio = read_bioinfo(T1PLUS_BIOINFO)
    with pytest.raises(BarcodeLayoutError):
        _ = barcode_geometry(bio, READ_LEN, 12, 8)  # first block is only 10 cycles


def test_geometry_refuses_a_read_with_no_insert_left():
    bio = read_bioinfo(T1PLUS_BIOINFO)
    with pytest.raises(BarcodeLayoutError):
        _ = barcode_geometry(bio, 18, 10, 8)


def test_bioinfo_without_barcode_cycles_is_an_error(tmp_path):
    bioinfo = tmp_path / "BioInfo.csv"
    _ = bioinfo.write_text("Machine ID,INV-MGI-T1\nRead1Len,100\nRead2Len,0\n")
    with pytest.raises(BioInfoError):
        _ = read_bioinfo(str(bioinfo))


def test_bioinfo_declaring_only_a_dual_barcode_is_refused(tmp_path):
    """The primary barcode length is mandatory.

    Without this, the block list collapses to `[DualBarcode]` and `bio.blocks[0]` -
    which every offset is measured from - becomes the *dual* barcode. A single-index
    sheet would then anchor against the wrong block's width and decode nothing,
    which is the silent whole-lane failure this module exists to prevent. A run of
    that shape has never been observed; refusing it is cheaper than reasoning about
    it.
    """
    bioinfo = tmp_path / "BioInfo.csv"
    _ = bioinfo.write_text(
        "Machine ID,INV-MGI-T1\nRead1Len,100\nRead2Len,0\nDualBarcodeLen,8\n"
    )
    with pytest.raises(BioInfoError):
        _ = read_bioinfo(str(bioinfo))


def test_derive_layout_from_sequencing_mode():
    """Derived from SE-vs-PE, not searched for.

    An Illumina-converted library's barcode region is one forward-native block
    5'-[i7][i5]-3'. SE reads the top strand directly; PE read 2 reads its exact
    reverse complement, which reverses the slot order as well as the bases.
    """
    assert derive_layout(is_pe=False) == ((FORWARD, FORWARD), INDEX_FIRST)
    assert derive_layout(is_pe=True) == ((REVCOMP, REVCOMP), INDEX2_FIRST)


def test_mgi_native_libraries_are_refused_rather_than_guessed_at():
    with pytest.raises(NotImplementedError):
        _ = derive_layout(is_pe=False, library_type=LIBRARY_TYPE_MGI)


def test_oriented_barcode_absorbs_orientation_and_slot_order():
    """Both go into the -B file's *content*, so the -b offsets stay pure geometry."""
    assert (
        oriented_barcode(INDEX, INDEX2, (FORWARD, FORWARD), INDEX_FIRST)
        == INDEX + INDEX2
    )
    assert oriented_barcode(INDEX, INDEX2, (REVCOMP, REVCOMP), INDEX2_FIRST) == revcomp(
        INDEX2
    ) + revcomp(INDEX)


def test_oriented_barcode_is_index_then_index2_for_a_t1plus_se_lane():
    """i7 then i5 - the *opposite* order to the vendor NovaSeqi5x8i7x10.csv.

    That file must not be fed to splitBarcode: it lists every UDP and concatenates
    i5+i7.
    """
    assert oriented_barcode(INDEX, INDEX2, (FORWARD, FORWARD), INDEX_FIRST).startswith(
        INDEX
    )


def test_format_b_args():
    assert format_b_args([(100, 10, 1), (110, 8, 1)]) == "-b 100 10 1 -b 110 8 1"


def _write_fastq(path, reads):
    with gzip.open(path, "wt") as f:
        for n, seq in enumerate(reads):
            _ = f.write("@read%d\n%s\n+\n%s\n" % (n, seq, "I" * len(seq)))
    return str(path)


def _se_read(index, index2, insert_len=100):
    """A T1+ SE read: insert, then the barcode blocks at the end, forward."""
    return "A" * insert_len + index + index2


def test_verify_layout_confirms_the_derived_layout_against_the_reads(tmp_path):
    bio = read_bioinfo(T1PLUS_BIOINFO)
    fastq = _write_fastq(tmp_path / "L01.fq.gz", [_se_read(INDEX, INDEX2)] * 200)

    layout = verify_layout(
        fastq, bio, [(INDEX, INDEX2)], (FORWARD, FORWARD), INDEX_FIRST
    )

    assert layout.offset == 100
    assert layout.offset2 == 110
    assert layout.read_len == READ_LEN
    assert layout.hits >= 50
    assert layout.sibling_hits == 0


def _symmetric_bioinfo(tmp_path, block_len=10):
    """A T1+ SE BioInfo whose two barcode blocks are the same width.

    The reverse-strand sibling swaps the slot widths, so it only *fits* when the two
    blocks are equally wide - see the asymmetric test below.
    """
    bioinfo = tmp_path / "BioInfo.csv"
    _ = bioinfo.write_text(
        "Machine ID,INV-MGI-T1\nRead1Len,100\nRead2Len,0\nBarcodeLen,%d\nDualBarcodeLen,%d\n"
        % (block_len, block_len)
    )
    return read_bioinfo(str(bioinfo))


def test_verify_layout_aborts_when_the_reads_match_the_opposite_strand(tmp_path):
    """A specific diagnosis, not a generic low hit count.

    This is what catches an SE/PE mislabelling in BioInfo.csv, or an MGI-native
    library put through the Illumina-converted derivation.
    """
    bio = _symmetric_bioinfo(tmp_path)
    index, index2 = "CTAGTGCTCT", "CCAACAGACT"  # both 10, so the sibling geometry fits

    # Reads carrying the reverse-strand sibling layout: rc(index2) + rc(index).
    fastq = _write_fastq(
        tmp_path / "L01.fq.gz",
        [_se_read(revcomp(index2), revcomp(index))] * 200,
    )

    with pytest.raises(BarcodeLayoutError, match="opposite strand"):
        _ = verify_layout(
            fastq, bio, [(index, index2)], (FORWARD, FORWARD), INDEX_FIRST
        )


def test_an_impossible_sibling_reads_as_low_evidence_not_opposite_strand(tmp_path):
    """Documents a real limit of the opposite-strand tripwire.

    The sibling swaps the two slot widths, so on asymmetric blocks - the reference
    run's 10 + 8 - a 10-base index2 will not fit the 8-cycle second block and the
    sibling cannot be scored at all. An opposite-strand lane of that shape therefore
    reports low evidence rather than the specific diagnosis. Still loud, still
    refused; just less informative.
    """
    bio = read_bioinfo(T1PLUS_BIOINFO)  # blocks 10 + 8
    fastq = _write_fastq(
        tmp_path / "L01.fq.gz", [_se_read(revcomp(INDEX2), revcomp(INDEX))] * 200
    )

    with pytest.raises(BarcodeLayoutError, match="not where"):
        _ = verify_layout(
            fastq,
            bio,
            [(INDEX, INDEX2)],
            (FORWARD, FORWARD),
            INDEX_FIRST,
            max_scan_reads=200,
        )


def test_verify_layout_aborts_when_the_sheet_does_not_match_the_run(tmp_path):
    bio = read_bioinfo(T1PLUS_BIOINFO)
    fastq = _write_fastq(tmp_path / "L01.fq.gz", [_se_read("TTTTTTTTTT", "TTTTTTTT")] * 200)

    with pytest.raises(BarcodeLayoutError, match="not where"):
        _ = verify_layout(
            fastq,
            bio,
            [(INDEX, INDEX2)],
            (FORWARD, FORWARD),
            INDEX_FIRST,
            max_scan_reads=200,
        )


def test_verify_layout_counts_evidence_absolutely_so_a_small_batch_still_passes(tmp_path):
    """Evidence is an absolute hit count, not a rate.

    The sheet defines the batch, so a rate would measure the batch's share of its
    lane rather than whether the layout is right. A one-sample sheet in a busy lane
    must pass as readily as a full one.
    """
    bio = read_bioinfo(T1PLUS_BIOINFO)
    ours = [_se_read(INDEX, INDEX2)] * 60
    others = [_se_read("GGGGGGGGGG", "GGGGGGGG")] * 4000
    fastq = _write_fastq(tmp_path / "L01.fq.gz", ours + others)

    layout = verify_layout(
        fastq, bio, [(INDEX, INDEX2)], (FORWARD, FORWARD), INDEX_FIRST
    )

    assert layout.hits >= 50
    assert layout.hit_rate < 0.05  # a rate-based gate would have failed this


def test_verify_layout_requires_a_complete_pair_from_one_sample(tmp_path):
    """Not two indices matched independently.

    A read whose slot 1 belongs to one sample and slot 2 to another is not a hit -
    otherwise a lane of shuffled halves would look like a clean match.
    """
    bio = read_bioinfo(T1PLUS_BIOINFO)
    other_index, other_index2 = "GATCAAGGCA", "TTGGTGAG"  # SQ5421
    fastq = _write_fastq(tmp_path / "L01.fq.gz", [_se_read(INDEX, other_index2)] * 200)

    with pytest.raises(BarcodeLayoutError):
        _ = verify_layout(
            fastq,
            bio,
            [(INDEX, INDEX2), (other_index, other_index2)],
            (FORWARD, FORWARD),
            INDEX_FIRST,
            max_scan_reads=200,
        )


def test_barcode_params_takes_only_the_bases_the_sheet_uses(tmp_path):
    """A block with unused trailing cycles yields a -b of the *index* width.

    T1+ can sequence 12 cycles where the sheet supplies 8; the 4 junk cycles must
    never be read.
    """
    bioinfo = tmp_path / "BioInfo.csv"
    _ = bioinfo.write_text(
        "Machine ID,INV-MGI-T1\nRead1Len,100\nRead2Len,0\nBarcodeLen,12\nDualBarcodeLen,8\n"
    )
    bio = read_bioinfo(str(bioinfo))
    index, index2 = "ACGTACGT", "TTTTAAAA"  # 8 and 8
    fastq = _write_fastq(
        tmp_path / "L01.fq.gz",
        # 12-cycle block holding an 8-base index, so 4 cycles of filler after it.
        ["A" * 100 + index + "NNNN" + index2] * 200,
    )

    layout = verify_layout(fastq, bio, [(index, index2)], (FORWARD, FORWARD), INDEX_FIRST)

    assert barcode_params(layout, mismatch=1) == [(100, 8, 1), (112, 8, 1)]


def test_write_barcode_file_is_idempotent(tmp_path):
    """Rewriting an unchanged -B file would force a full re-demultiplex.

    redun hashes a local File as `hash_struct(["File", "local", path, size, mtime])` -
    an O(1) pseudo-hash, NOT the content. So rewriting identical bytes still changes
    the hash, which changes `split_barcodes_one`'s argument hash, misses the cache,
    and re-runs a ~25 minute splitBarcode job per lane on every launch.

    Since stage 1 regenerates the barcode files on every launch, leaving mtime alone
    when nothing changed is what makes reruns cache correctly.

    mtime is stamped explicitly rather than compared against the clock: consecutive
    writes can land in the same filesystem tick, which would let this pass without
    the behaviour being implemented at all.
    """
    path = str(tmp_path / "L01.barcodes")
    entries = [("SQ5420", "CTAGTGCTCTCCAACAGA"), ("SQ5421", "GATCAAGGCATTGGTGAG")]
    marker = 1_000_000_000  # a distinctive mtime well in the past

    _ = write_barcode_file(entries, path)
    os.utime(path, (marker, marker))

    _ = write_barcode_file(entries, path)
    assert os.stat(path).st_mtime == marker, "unchanged content must not be rewritten"
    assert open(path).read().startswith("SQ5420\t")


def test_write_barcode_file_rewrites_when_the_barcodes_change(tmp_path):
    path = str(tmp_path / "L01.barcodes")
    marker = 1_000_000_000

    _ = write_barcode_file([("SQ5420", "CTAGTGCTCTCCAACAGA")], path)
    os.utime(path, (marker, marker))

    _ = write_barcode_file([("SQ5420", "AAAAAAAAAACCCCCCCC")], path)
    assert os.stat(path).st_mtime != marker
    assert "AAAAAAAAAACCCCCCCC" in open(path).read()


# --------------------------------------------------------------------------
# Reporting observed barcodes in the sheet's own terms
#
# These are the tests for the operator-facing half of the check: when the reads and the
# sheet disagree, what is quoted back has to be what the operator would type into the
# sheet, not what the instrument wrote.
# --------------------------------------------------------------------------

# Real runs, reduced to their sample sheet plus the barcode file the demultiplexer was
# actually given. The barcode file holds each sample's barcode exactly as it appears in
# the reads, so together they are ground truth for the read -> sheet direction across
# all three geometries in production.
REAL_RUNS = [
    ("DL100018469.csv", "DL100018469.L01.barcodes", "BioInfo-T1plus-SE.csv"),
    ("FT150034703-head.csv", "FT150034703-head.L01.barcodes", "BioInfo-G99-SE.csv"),
    ("DL100018466.csv", "DL100018466.L01.barcodes", "BioInfo-T1plus-PE.csv"),
]


def _real_run(sheet_name, barcodes_name, bioinfo_name):
    """`(sheet rows by sample, observed barcodes by sample, layout)` for a real run."""
    sheet = read_sample_sheet(os.path.join(HERE, sheet_name))
    id_column, index_column, index2_column = _sheet_columns(sheet)
    rows = {
        row[id_column].strip(): (
            row[index_column].strip().upper(),
            (row.get(index2_column, "") or "").strip().upper() if index2_column else "",
        )
        for row in samples_for_lane(sheet, 1)
    }
    observed = dict(
        line.rstrip("\n").split("\t")
        for line in open(os.path.join(HERE, barcodes_name))
    )
    bio = read_bioinfo(os.path.join(HERE, bioinfo_name))
    return rows, observed, derive_layout(bio.is_pe)


@pytest.mark.parametrize("sheet_name,barcodes_name,bioinfo_name", REAL_RUNS)
def test_observed_barcodes_reproduce_the_sample_sheet(
    sheet_name, barcodes_name, bioinfo_name
):
    """Every barcode in a real run's barcode file maps back to that sheet's own columns.

    The headline requirement, against production data rather than synthesis: T1+ SE
    (10 + 8), G99 SE (8 + 10, blocks the other way round) and T1+ PE (revcomp,
    index2-first). If `sheet_indices` is wrong in any of orientation, slot order or
    slot width, one of these three fails.
    """
    rows, observed, (orientation, slot_order) = _real_run(
        sheet_name, barcodes_name, bioinfo_name
    )
    assert observed, "fixture has no barcodes"

    for sample_id, barcode in observed.items():
        index, index2 = rows[sample_id]
        # Forward: the fixture's own barcode file is what oriented_barcode must produce.
        assert oriented_barcode(index, index2, orientation, slot_order) == barcode
        # Back again: which is what an operator gets shown.
        assert sheet_indices(
            barcode, orientation, slot_order, len(index), len(index2)
        ) == (index, index2), sample_id


def test_a_misinverted_barcode_would_name_a_different_real_sample():
    """Why the inversion is pinned by a test rather than by inspection.

    DL100018466 pairs its i7/i5 combinatorially, so every sample's (index, index2) also
    appears as some *other* sample's (index2, index). An inversion that drops the
    index2-first swap therefore never produces an invalid-looking barcode - it silently
    re-labels reads as a different, real sample. Measured on that run's read 2: wrong on
    100% of decodable reads, visibly wrong on none of them.
    """
    rows, observed, (orientation, slot_order) = _real_run(*REAL_RUNS[2])
    by_pair = {pair: sample for sample, pair in rows.items()}

    misattributed = 0
    for sample_id, barcode in observed.items():
        index, index2 = rows[sample_id]
        slot1, slot2 = barcode[: len(index2)], barcode[len(index2) :]
        naive = (revcomp(slot1), revcomp(slot2))  # forgot the index2-first swap
        assert naive != (index, index2)
        if by_pair.get(naive) not in (None, sample_id):
            misattributed += 1

    assert misattributed == len(observed), (
        "expected every row of this fixture to be swap-degenerate, so that a wrong "
        "inversion is silent rather than obvious"
    )
    # And the real thing does not do that.
    for sample_id, barcode in observed.items():
        index, index2 = rows[sample_id]
        assert by_pair[
            sheet_indices(barcode, orientation, slot_order, len(index), len(index2))
        ] == sample_id


@pytest.mark.parametrize("orientation,slot_order", list(_COHERENT_LAYOUTS))
@pytest.mark.parametrize("index2", [INDEX2, ""])
def test_sheet_indices_is_the_exact_inverse_of_oriented_barcode(
    orientation, slot_order, index2
):
    """Round trip for both physically possible layouts, dual- and single-index.

    The single-index case is the one the real fixtures cannot cover: `_slot_lengths`
    collapses to one slot regardless of order, so an inversion that always swaps would
    report the index in the index2 column.
    """
    barcode = oriented_barcode(INDEX, index2, orientation, slot_order)
    assert sheet_indices(
        barcode, orientation, slot_order, len(INDEX), len(index2)
    ) == (INDEX, index2)


def _sheet_file(tmp_path, rows, name="SHEET.csv"):
    """A minimal MGI sheet: `rows` is `[(sample_id, index, index2), ...]`, all lane 1."""
    path = tmp_path / name
    lines = ["[Header]", "Flowcell,RUN01", "", "[Reads]", "100", "", "[Data]",
             "Lanes,Sample_ID,index,index2"]
    lines += ["1,%s,%s,%s" % row for row in rows]
    _ = path.write_text("\n".join(lines) + "\n")
    return read_sample_sheet(str(path))


def _run_dir(tmp_path, reads, bioinfo_text, run="RUN01"):
    """A run directory holding one SE lane, as `read_files`/`bioinfo_path` expect."""
    lane_dir = tmp_path / run / "L01"
    lane_dir.mkdir(parents=True)
    _ = (lane_dir / "BioInfo.csv").write_text(bioinfo_text)
    _ = _write_fastq(lane_dir / ("%s_L01_read.fq.gz" % run), reads)
    return str(tmp_path / run)


T1PLUS_SE_BIOINFO_TEXT = (
    "Machine ID,INV-MGI-T1\nRead1Len,100\nRead2Len,0\nBarcodeLen,10\nDualBarcodeLen,8\n"
)


def test_a_reverse_complemented_index2_column_is_named_as_such(tmp_path):
    """The commonest operator error, and the one the old message was silent about.

    The two Illumina i5 workflow conventions differ in exactly this column, so a sheet
    exported for the wrong one fails with every barcode intact and merely mirrored.
    """
    bio = read_bioinfo(T1PLUS_BIOINFO)
    fastq = _write_fastq(
        tmp_path / "L01.fq.gz", [_se_read(INDEX, revcomp(INDEX2))] * 200
    )

    with pytest.raises(BarcodeLayoutError) as excinfo:
        _ = verify_layout(
            fastq, bio, [(INDEX, INDEX2)], (FORWARD, FORWARD), INDEX_FIRST,
            max_scan_reads=200,
        )

    message = str(excinfo.value)
    assert "index2 (i5) column is reverse-complemented" in message
    assert "FIX: reverse-complement the index2 column" in message


def test_swapped_index_columns_are_named_as_such(tmp_path):
    """Equal-width blocks, so the swap actually fits and can be scored."""
    bio = _symmetric_bioinfo(tmp_path)
    index, index2 = "CTAGTGCTCT", "CCAACAGACT"
    fastq = _write_fastq(tmp_path / "L01.fq.gz", [_se_read(index2, index)] * 200)

    with pytest.raises(BarcodeLayoutError) as excinfo:
        _ = verify_layout(
            fastq, bio, [(index, index2)], (FORWARD, FORWARD), INDEX_FIRST,
            max_scan_reads=200,
        )

    assert "index and index2 columns are swapped" in str(excinfo.value)


def test_a_rewrite_that_cannot_fit_the_blocks_is_reported_as_untestable(tmp_path):
    """Not as a zero - "nothing matched" must not claim more than was checked.

    The reference run's blocks are 10 + 8, so swapping a 10-base index with an 8-base
    index2 gives slot widths that do not fit, and the swap has no offsets to score at.
    Same limitation the reverse-strand sibling has on asymmetric blocks.
    """
    bio = read_bioinfo(T1PLUS_BIOINFO)  # blocks 10 + 8, INDEX is 10 and INDEX2 is 8
    fastq = _write_fastq(tmp_path / "L01.fq.gz", [_se_read("TTTTTTTTTT", "TTTTTTTT")] * 200)

    with pytest.raises(BarcodeLayoutError) as excinfo:
        _ = verify_layout(
            fastq, bio, [(INDEX, INDEX2)], (FORWARD, FORWARD), INDEX_FIRST,
            max_scan_reads=200,
        )

    message = str(excinfo.value)
    assert "not testable on this lane's block widths" in message
    assert "index and index2 columns are swapped" in message.split(
        "not testable on this lane's block widths"
    )[1]


def test_the_census_reports_barcodes_in_sheet_orientation_not_read_orientation(tmp_path):
    """Under the PE derivation the two differ, which is the whole point of the census.

    A census that quoted the read slice would be handing the operator a string that
    appears nowhere in their sheet and cannot be pasted into one.
    """
    bio = read_bioinfo(os.path.join(HERE, "BioInfo-T1plus-PE.csv"))
    index, index2 = "TTACCGAC", "CGAATACG"  # ZV0157752, from the real run
    orientation, slot_order = derive_layout(is_pe=True)
    observed = oriented_barcode(index, index2, orientation, slot_order)
    # PE read 2: 150 bp insert, then two 10-cycle blocks holding 8-base indices.
    read = "A" * 150 + observed[:8] + "NN" + observed[8:] + "NN"
    fastq = _write_fastq(tmp_path / "L01.fq.gz", [read] * 200)

    with pytest.raises(BarcodeLayoutError) as excinfo:
        _ = verify_layout(
            fastq, bio, [("GGGGGGGG", "GGGGGGGG")], orientation, slot_order,
            max_scan_reads=200,
        )

    message = str(excinfo.value)
    assert "%s %s" % (index, index2) in " ".join(message.split()), message
    assert observed not in message.split("OBSERVED BARCODES")[1]


def test_polyt_is_reported_but_polyg_is_folded_away(tmp_path):
    """PolyG/N is MGI's no-signal call; polyA/polyT is signal.

    Folding every single-base run would make a lane that really is full of polyT report
    "nothing observed", which is worse than useless.
    """
    bio = read_bioinfo(T1PLUS_BIOINFO)
    reads = [_se_read("TTTTTTTTTT", "TTTTTTTT")] * 120 + [
        _se_read("GGGGGGGGGG", "GGGGGGGG")
    ] * 400
    fastq = _write_fastq(tmp_path / "L01.fq.gz", reads)

    with pytest.raises(BarcodeLayoutError) as excinfo:
        _ = verify_layout(
            fastq, bio, [(INDEX, INDEX2)], (FORWARD, FORWARD), INDEX_FIRST,
            max_scan_reads=600,
        )

    census = str(excinfo.value).split("OBSERVED BARCODES")[1]
    assert "TTTTTTTTTT TTTTTTTT" in " ".join(census.split())
    assert "GGGGGGGGGG GGGGGGGG" not in " ".join(census.split())
    assert "polyG/N no-signal" in census


# Ten distinct 10-base i7s whose reverse complements are all distinct from each other
# and from the originals, so a wholesale rc of the column collides only where a test
# arranges it to.
I7S = [
    "ACGTACGTAC", "ACGTACGTCA", "ACGTACGTGA", "ACGTACGTTA", "ACGTACGACA",
    "ACGTACGCAA", "ACGTACGGAA", "ACGTACGTAG", "ACGTACGTAT", "ACGTACGTCC",
]
I5 = "CCAACAGA"


def test_lane_plan_names_the_sample_whose_barcode_never_appeared(tmp_path, caplog):
    """A barcode is only actionable with the sample it belongs to.

    `index_pairs` drops Sample_ID by construction, so the warning is only useful
    because `lane_plan` joins the unobserved barcodes back to the sheet.
    """
    sheet = _sheet_file(
        tmp_path, [("PRESENT", INDEX, INDEX2), ("ABSENT", I7S[0], I5)]
    )
    run_dir = _run_dir(tmp_path, [_se_read(INDEX, INDEX2)] * 200, T1PLUS_SE_BIOINFO_TEXT)

    with caplog.at_level(logging.WARNING):
        _ = lane_plan(sheet, 1, run_dir, "RUN01")

    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("ABSENT" in w for w in warnings), warnings
    assert not any("PRESENT" in w for w in warnings)


def test_a_healthy_lane_says_every_barcode_was_seen(tmp_path, caplog):
    """The reassuring line an operator gets when nothing is wrong."""
    sheet = _sheet_file(tmp_path, [("A", INDEX, INDEX2), ("B", I7S[0], I5)])
    reads = [_se_read(INDEX, INDEX2)] * 100 + [_se_read(I7S[0], I5)] * 100
    run_dir = _run_dir(tmp_path, reads, T1PLUS_SE_BIOINFO_TEXT)

    with caplog.at_level(logging.INFO):
        _ = lane_plan(sheet, 1, run_dir, "RUN01")

    messages = [r.getMessage() for r in caplog.records]
    assert any("all 2 listed barcodes observed" in m for m in messages), messages
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_systematically_wrong_sheet_that_clears_the_hit_gate_is_still_caught(
    tmp_path, caplog
):
    """The gap this closes, reproduced from a real run.

    On FT150034703 L01, reverse-complementing the whole i7 column still scores 8637
    hits - 34 of the rewritten barcodes collide with real ones, and those few samples'
    reads are enough to clear min_hits. The layout check passes and ~99% of the lane
    would go to `undecoded`. Only coverage notices: 244 of 3788 barcodes were ever seen.

    Same shape here in miniature: ten samples whose i7 is reverse-complemented, plus two
    rows that collide with real barcodes and carry the hit count over the gate.
    """
    rows = [("RC%d" % n, revcomp(i7), I5) for n, i7 in enumerate(I7S)]
    rows += [("COLLIDE0", I7S[0], I5), ("COLLIDE1", I7S[1], I5)]
    sheet = _sheet_file(tmp_path, rows)
    reads = [read for i7 in I7S for read in [_se_read(i7, I5)] * 30]
    run_dir = _run_dir(tmp_path, reads, T1PLUS_SE_BIOINFO_TEXT)

    with caplog.at_level(logging.WARNING):
        plan = lane_plan(sheet, 1, run_dir, "RUN01")

    # It passed the hit gate, exactly as the real run did.
    assert plan.layout.hits >= 50
    warnings = " ".join(
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    )
    assert "index (i7) column is reverse-complemented" in warnings, warnings
    assert "undecoded" in warnings


def test_a_coverage_scan_that_hits_its_cap_says_so_rather_than_accusing_a_row(tmp_path):
    """Absence is not evidence when the scan stopped early.

    Per-sample yield has a long tail - on FT150034703 a healthy lane still has 172 of
    3788 barcodes unseen at 5x coverage - so a capped scan must report its depth, not
    imply the rows are wrong.
    """
    bio = read_bioinfo(T1PLUS_BIOINFO)
    fastq = _write_fastq(tmp_path / "L01.fq.gz", [_se_read(INDEX, INDEX2)] * 200)

    layout = verify_layout(
        fastq, bio, [(INDEX, INDEX2), (I7S[0], I5)], (FORWARD, FORWARD), INDEX_FIRST,
        coverage_max_scan_reads=100,
    )

    assert layout.coverage_exhausted
    assert not layout.coverage_complete
    assert not layout.coverage_diagnosis


# --------------------------------------------------------------------------
# Opt-in: the real reads, which are far too large to commit
# --------------------------------------------------------------------------

SEQ_ROOT = "/projects/2026_sequence_production_a"
needs_real_reads = pytest.mark.skipif(
    not os.path.isdir(os.path.join(SEQ_ROOT, "run_data")),
    reason="real MGI runs not available on this machine",
)


@needs_real_reads
@pytest.mark.parametrize(
    "run,expected_b_args",
    [
        ("DL100018466", "-b 300 8 1 -b 310 8 1"),
        ("FT150034703", "-b 100 8 1 -b 108 10 1"),
    ],
)
def test_lane_plan_reproduces_the_recorded_barcode_parameters(run, expected_b_args):
    """The -b arguments are the thing that must not move.

    Ground truth is the `barcode_parameters` file the run was actually demultiplexed
    with; a diagnostic change that shifted an offset would be a far worse regression
    than the missing diagnostics it set out to fix.
    """
    sheet = read_sample_sheet(
        os.path.join(SEQ_ROOT, "postprocessing/mgi", run, "SampleSheet.csv")
    )
    plan = lane_plan(sheet, 1, os.path.join(SEQ_ROOT, "run_data", run), run)

    assert format_b_args(plan.params) == expected_b_args
    # Both of these lanes are healthy, so every listed barcode should turn up.
    assert plan.layout.coverage_complete


@needs_real_reads
def test_a_reverse_complemented_i5_column_is_diagnosed_on_a_real_run():
    """End to end on DL100018466 read 2, with the sheet's i5 column mirrored."""
    sheet = read_sample_sheet(
        os.path.join(SEQ_ROOT, "postprocessing/mgi/DL100018466/SampleSheet.csv")
    )
    bio = read_bioinfo(
        os.path.join(SEQ_ROOT, "run_data/DL100018466/L01/BioInfo.csv")
    )
    fastq = os.path.join(
        SEQ_ROOT, "run_data/DL100018466/L01/DL100018466_L01_read_2.fq.gz"
    )
    orientation, slot_order = derive_layout(bio.is_pe)
    broken = [(index, revcomp(index2)) for index, index2 in index_pairs(sheet, 1)]

    with pytest.raises(BarcodeLayoutError) as excinfo:
        _ = verify_layout(
            fastq, bio, broken, orientation, slot_order, max_scan_reads=20000
        )

    message = str(excinfo.value)
    assert "index2 (i5) column is reverse-complemented" in message

    # Every barcode the census quotes must be a row of the *unmodified* sheet, written
    # the way that sheet writes it. This lane pairs its i7/i5 combinatorially, so an
    # inversion that mixed up the slots would still yield real-looking pairs - they
    # would just belong to the wrong samples - and would fail here rather than silently.
    true_pairs = set(index_pairs(sheet, 1))
    census = message.split("OBSERVED BARCODES")[1].splitlines()
    quoted = [
        (fields[2], fields[3])
        for fields in (line.split() for line in census)
        if len(fields) >= 4 and fields[0].isdigit()
    ]
    assert len(quoted) == 20, quoted
    assert all(pair in true_pairs for pair in quoted), [
        pair for pair in quoted if pair not in true_pairs
    ]


def test_the_census_separates_mistyped_rows_from_the_good_ones(tmp_path):
    """The case the sample naming exists for: a sheet that is mostly right.

    A wholly-wrong sheet lists none of the barcodes present, so every census row reads
    "not in sheet" and the naming adds nothing. It earns its keep here, where four rows
    are correct and one is mistyped: the operator needs to see which is which, not a
    flat list of barcodes.
    """
    good = [("S%d" % n, i7, I5) for n, i7 in enumerate(I7S[:4])]
    sheet_rows = good + [("MISTYPED", I7S[4], I5)]
    # The reads carry the four good barcodes, plus one barcode nobody listed - what the
    # mistyped row's sample really went out with.
    unlisted = I7S[5]
    reads = [read for _, i7, _ in good for read in [_se_read(i7, I5)] * 60]
    reads += [_se_read(unlisted, I5)] * 200

    bio = read_bioinfo(T1PLUS_BIOINFO)
    fastq = _write_fastq(tmp_path / "L01.fq.gz", reads)
    sheet = _sheet_file(tmp_path, sheet_rows)
    sample_ids = sample_ids_by_index(sheet, 1)

    # Forced to report by asking for more evidence than this lane can offer.
    with pytest.raises(BarcodeLayoutError) as excinfo:
        _ = verify_layout(
            fastq, bio, [(i7, I5) for _, i7, _ in sheet_rows],
            (FORWARD, FORWARD), INDEX_FIRST,
            min_hits=10**6, max_scan_reads=len(reads), sample_ids=sample_ids,
        )

    census = str(excinfo.value).split("OBSERVED BARCODES")[1]
    # count, share, index, index2, then the sheet row (which may contain spaces).
    rows = {
        fields[2]: " ".join(fields[4:])
        for fields in (line.split() for line in census.splitlines())
        if len(fields) >= 5 and fields[0].isdigit()
    }
    # The four listed barcodes are named; the one nobody listed is called out.
    for name, i7, _ in good:
        assert rows[i7] == name, census
    assert rows[unlisted].startswith("**"), census
    assert I7S[4] not in rows, "the mistyped row's barcode is not in the reads at all"
