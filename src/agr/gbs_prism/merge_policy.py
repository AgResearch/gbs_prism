"""Which of a library's lanes to merge, and when to refuse the library.

Stdlib-only, so this stays CI-testable; `agr.redun.tasks.merge_fastq` is only the
redun wrapper around it.

**The problem this solves.** MGI leaves splitBarcode's output per lane, and a
library's lanes are merged into the single fastq the GBS link farm needs. When a lane
produces little or nothing for a library, two situations look identical on disk and
want opposite handling:

* **demultiplexing failed for that lane** - merging the rest silently halves the
  library's depth, and KGD gets a library that looks whole but is not;
* **the library legitimately underperformed in that lane** - ordinary wet-lab
  variation, and no reason to throw away an otherwise usable library.

**What tells them apart** is the depth of the *merged* result. A GBS library needs a
minimum number of reads to be worth analysing; below that it is not viable however
the shortfall arose, and above it the shortfall did not matter. So the rule is a
threshold on the library total rather than on any individual lane - which is the
right shape anyway, because lanes are merged and it is the merged depth that
downstream analysis sees.

Read counts come from each lane's `BarcodeStat.txt`, which reports them per library
exactly (see `agr.seq.mgi.barcode_stat`), so nothing here has to read a fastq.
"""

import logging

logger = logging.getLogger(__name__)

# Minimum reads for a GBS sequencing library to be worth analysing, across all of its
# lanes once merged. Below this the library is refused rather than passed to KGD.
MIN_LIBRARY_READS = 100_000


class MergePolicyError(Exception):
    pass


def lanes_to_merge(
    library: str,
    expected_lanes: list[int],
    found: dict[int, str],
    read_counts: dict[int, int],
) -> list[str]:
    """The fastq paths to merge for one library, in lane order.

    `expected_lanes` is what the sample sheet says the library was sequenced in;
    `found` maps lane to the fastq splitBarcode produced (absent when it produced
    none); `read_counts` maps lane to the library's read count there, from
    `BarcodeStat.txt` (a missing entry counts as zero, which is what a lane with no
    output means).

    Raises `MergePolicyError` when the library's total is below
    `MIN_LIBRARY_READS`. A shortfall in one lane is only reported, because the merged
    total is what matters.
    """
    if not found:
        raise MergePolicyError(
            "library %s: splitBarcode produced no fastq in any of its lanes (%s). "
            "Either demultiplexing failed for this library or the sample sheet "
            "disagrees with the run."
            % (library, ", ".join("L%02d" % lane for lane in expected_lanes))
        )

    total = sum(read_counts.get(lane, 0) for lane in expected_lanes)

    if total < MIN_LIBRARY_READS:
        raise MergePolicyError(
            "library %s has only %s reads across %s, below the %s needed for a "
            "usable GBS library. Per lane: %s. Merging would hand downstream "
            "analysis a library that looks whole but is not, so this is refused - "
            "check whether demultiplexing failed for this library."
            % (
                library,
                "{:,}".format(total),
                ", ".join("L%02d" % lane for lane in expected_lanes),
                "{:,}".format(MIN_LIBRARY_READS),
                ", ".join(
                    "L%02d: %s" % (lane, "{:,}".format(read_counts.get(lane, 0)))
                    for lane in expected_lanes
                ),
            )
        )

    # Report anything the sheet expected but which yielded nothing. Not fatal - the
    # library has cleared the bar without it - but worth seeing, since a systematic
    # pattern across libraries points at that lane rather than at the libraries.
    if empty := [lane for lane in expected_lanes if lane not in found]:
        logger.warning(
            "library %s: no fastq from %s, merging the remaining %d lane(s); "
            "total %s reads still clears the %s minimum",
            library,
            ", ".join("L%02d" % lane for lane in empty),
            len(found),
            "{:,}".format(total),
            "{:,}".format(MIN_LIBRARY_READS),
        )

    return [found[lane] for lane in sorted(found)]
