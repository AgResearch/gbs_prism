"""splitBarcode's `BarcodeStat.txt` -> MultiQC custom content.

Ported from `mgi_prism/workflow/scripts/barcodestat_to_multiqc.py`. **Keep this
module stdlib-only**, so it stays CI-testable.

This is the MGI analog of the five bcl-convert metrics files the Illumina report
used. MultiQC has no splitBarcode parser and no plugin to write one into, so the
stats reach the report as *custom content*: a `*_mqc.txt` file whose leading
`# key: value` block is the section config and whose body is the data. MultiQC finds
it on the search path like any other report.

Two sections, because the questions differ:

* `mgi_demux_lane` - **bargraph**, one group per lane, of correct / corrected /
  undecoded reads. The headline "did the run demultiplex" number, only ever 1-8 bars.
* `mgi_demux_sample` - **table**, one row per sample. Deliberately not a bargraph: a
  GBS lane has ~3800 samples, and the question asked of per-sample counts ("which
  samples dropped out") is a sort, not a shape. Above 500 rows MultiQC switches a
  table to a violin plot itself, which stays readable at 3800.

`BarcodeStat.txt` is tab-separated, values carry a leading space, sample rows are
prefixed with a literal `barcode`, and the file ends with a Total row:

    #Barcode         Correct    Corrected    Total       Percentage(%)
    barcodeSQ5420    323321751  13945596     337267347   50.617756
    Total            586028867  26383520     612412387   91.912071

Verified on FT150034703 L01 (SE, 3788 samples), DL100018466 L01-L04 (PE, 96
samples/lane) and DL100018469 (the reference run): the Total row is exactly the
column-wise sum of the sample rows, and Percentage is of *all* reads in the lane,
decoded or not - which is what makes the undecoded count recoverable.
"""

import logging
import os
import os.path

logger = logging.getLogger(__name__)

# The literal prefix splitBarcode prepends to every sample name. Confirmed against
# the .barcodes files for the verified runs: no real sample name starts with it, so
# stripping is unambiguous.
BARCODE_PREFIX = "barcode"

EXPECTED_HEADER = ["#Barcode", "Correct", "Corrected", "Total", "Percentage(%)"]

LANE_SECTION_FILENAME = "mgi_demux_lane_mqc.txt"
SAMPLE_SECTION_FILENAME = "mgi_demux_sample_mqc.txt"


class BarcodeStatError(Exception):
    """A BarcodeStat.txt that could not be read the way this parser expects."""


def parse_barcode_stat(
    path: str,
) -> tuple[list[tuple[str, int, int, int, float]], tuple[int, int, int, float]]:
    """Read one lane's `BarcodeStat.txt`.

    Returns `(samples, totals)`, where samples is
    `[(name, correct, corrected, total, percent), ...]` and totals is the file's own
    Total row as `(correct, corrected, total, percent)`.

    Fails loudly rather than guessing: a stat file that does not look like the
    verified runs means splitBarcode changed its output, and a half-parsed demux
    summary is worse than none.
    """
    with open(path) as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]

    if not lines:
        raise BarcodeStatError("%s: file is empty" % path)

    header = [field.strip() for field in lines[0].split("\t")]
    if header != EXPECTED_HEADER:
        raise BarcodeStatError(
            "%s: unexpected header %s, expected %s" % (path, header, EXPECTED_HEADER)
        )

    samples: list[tuple[str, int, int, int, float]] = []
    totals: tuple[int, int, int, float] | None = None

    for lineno, line in enumerate(lines[1:], start=2):
        fields = [field.strip() for field in line.split("\t")]
        if len(fields) != len(EXPECTED_HEADER):
            raise BarcodeStatError(
                "%s:%d: expected %d fields, got %d"
                % (path, lineno, len(EXPECTED_HEADER), len(fields))
            )
        name = fields[0]
        try:
            correct, corrected, total = (int(field) for field in fields[1:4])
            percent = float(fields[4])
        except ValueError as e:
            raise BarcodeStatError("%s:%d: non-numeric value - %s" % (path, lineno, e))

        if name == "Total":
            totals = (correct, corrected, total, percent)
            continue

        if not name.startswith(BARCODE_PREFIX):
            raise BarcodeStatError(
                "%s:%d: sample row %r does not start with %r - splitBarcode's naming "
                "has changed" % (path, lineno, name, BARCODE_PREFIX)
            )
        samples.append(
            (name[len(BARCODE_PREFIX) :], correct, corrected, total, percent)
        )

    if totals is None:
        raise BarcodeStatError("%s: no Total row - lane may not have finished" % path)
    if not samples:
        raise BarcodeStatError("%s: Total row present but no sample rows" % path)

    # The Total row is the sum of the sample rows on every verified run. If not, this
    # parser is misreading the file and every downstream number is suspect.
    summed = tuple(sum(row[index] for row in samples) for index in (1, 2, 3))
    if summed != totals[:3]:
        raise BarcodeStatError(
            "%s: sample rows sum to %s but Total row says %s"
            % (path, summed, totals[:3])
        )

    return samples, totals


def lane_read_counts(totals: tuple[int, int, int, float]) -> tuple[int, int, int]:
    """Split one lane into `(correct, corrected, undecoded)` read counts.

    `BarcodeStat.txt` never states the undecoded count, but Percentage is a share of
    all reads in the lane, so the lane total - and the undecoded remainder - follow
    from the Total row alone. Percentage has 6 decimal places, leaving the recovered
    figure accurate to a handful of reads at these counts: fine for a QC bar, and why
    it is rounded to an int rather than presented as exact.
    """
    correct, corrected, decoded, percent = totals
    if percent <= 0:
        raise BarcodeStatError(
            "Total row reports %s%% decoded - cannot recover the lane read count"
            % percent
        )
    lane_reads = decoded / (percent / 100.0)
    undecoded = max(int(round(lane_reads)) - decoded, 0)
    return correct, corrected, undecoded


def _write_mqc(
    path: str, config_lines: list[str], header: list[str], rows: list[tuple]
) -> str:
    """Write one MultiQC custom-content file.

    The leading `# ` block is YAML configuring the section; MultiQC reads it, strips
    it, and parses the rest as the data table.
    """
    with open(path, "w") as f:
        for line in config_lines:
            _ = f.write("# %s\n" % line if line else "#\n")
        _ = f.write("\t".join(header) + "\n")
        for row in rows:
            _ = f.write("\t".join(str(field) for field in row) + "\n")
    return path


_LANE_CONFIG = [
    "id: 'mgi_demux_lane'",
    "section_name: 'splitBarcode Demultiplexing'",
    "description: 'Reads assigned per lane by splitBarcode. <em>Correct</em> matched a"
    " sample barcode exactly; <em>Corrected</em> matched within the allowed mismatch;"
    " <em>Undecoded</em> matched no barcode and is written to the"
    " <code>undecoded</code> fastq, which is excluded from FastQC.'",
    "plot_type: 'bargraph'",
    "pconfig:",
    "    id: 'mgi_demux_lane_plot'",
    "    title: 'splitBarcode: reads per lane'",
    "    ylab: 'Reads'",
    "    cpswitch_counts_label: 'Number of reads'",
    # Without an explicit cats list MultiQC orders the stack by magnitude, which on
    # the verified runs put Undecoded *between* Correct and Corrected - the two that
    # together mean "decoded". Fixing the order keeps them adjacent, so the decoded
    # fraction reads as one block. Order is all that is settable: MultiQC 1.17 custom
    # content accepts a per-category color and then ignores it, so none is set.
    "    cats:",
    "        - Correct",
    "        - Corrected",
    "        - Undecoded",
]

_SAMPLE_CONFIG = [
    "id: 'mgi_demux_sample'",
    "section_name: 'splitBarcode Reads per Sample'",
    "description: 'Reads assigned to each sample by splitBarcode."
    " <em>PercentOfLane</em> is the share of all reads in that lane, decoded or not,"
    " so it sums to the lane decoding rate rather than to 100%. Sort by"
    " <em>Total</em> to find sample dropouts.'",
    "plot_type: 'table'",
    "pconfig:",
    "    id: 'mgi_demux_sample_table'",
    "    title: 'splitBarcode: reads per sample'",
    "    col1_header: 'Sample'",
]


def write_multiqc_custom_content(
    run: str, barcode_stats: dict[str, str], out_dir: str
) -> tuple[str, str]:
    """Write both custom-content sections, returning `(lane file, sample file)`.

    `barcode_stats` maps lane label (`L01`) to that lane's `BarcodeStat.txt`. The
    mapping is explicit so no lane name is ever inferred from a path.
    """
    os.makedirs(out_dir, exist_ok=True)

    lane_rows: list[tuple] = []
    sample_rows: list[tuple] = []

    for lane in sorted(barcode_stats):
        samples, totals = parse_barcode_stat(barcode_stats[lane])
        correct, corrected, undecoded = lane_read_counts(totals)
        lane_rows.append((lane, correct, corrected, undecoded))
        for name, s_correct, s_corrected, s_total, s_percent in samples:
            # Namespaced like the fastq files, so this row and the sample's FastQC
            # entry carry the same run/lane context - but deliberately not the *same*
            # MultiQC sample: PE FastQC has two entries (_1, _2) per sample against
            # one barcode row, so merging would misstate which read the counts
            # describe.
            sample_rows.append(
                (
                    "%s_%s_%s" % (run, lane, name),
                    lane,
                    s_correct,
                    s_corrected,
                    s_total,
                    "%.6f" % s_percent,
                )
            )
        logger.info(
            "%s %s: %d samples, %.3f%% of lane reads decoded",
            run,
            lane,
            len(samples),
            totals[3],
        )

    lane_file = _write_mqc(
        os.path.join(out_dir, LANE_SECTION_FILENAME),
        _LANE_CONFIG,
        ["Lane", "Correct", "Corrected", "Undecoded"],
        lane_rows,
    )
    sample_file = _write_mqc(
        os.path.join(out_dir, SAMPLE_SECTION_FILENAME),
        _SAMPLE_CONFIG,
        ["Sample", "Lane", "Correct", "Corrected", "Total", "PercentOfLane"],
        sample_rows,
    )

    logger.info(
        "wrote %d lane rows and %d sample rows to %s",
        len(lane_rows),
        len(sample_rows),
        out_dir,
    )
    return lane_file, sample_file
