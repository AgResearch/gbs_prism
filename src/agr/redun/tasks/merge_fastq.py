"""Merge a library's per-lane fastqs into the single fastq the GBS link farm needs.

This step has no prior art: `mgi_prism` is per-lane throughout and never merges.

**Why merge at all.** gquery's `Mgi.resolve_fastq_links` requires exactly one fastq
per library, and Tassel3 consumes a single `_s_1_` link. Merging here is what lets
everything downstream stay unaware of lanes.

**Why per library rather than per lane set.** Libraries are not in every lane: in the
reference run SQ5420/SQ5421 are in L01+L02 while SQ5575/SQ5576 are in L03+L04. A
blanket merge of all four lanes would mix unrelated libraries' reads. The lane set
comes from the sample sheet (`lanes_by_library`), and the code handles N lanes - T1+
has four and nothing stops a library spanning all of them.

**Why `cat` is correct.** gzip is a concatenating format: the concatenation of two
gzip members is itself a valid gzip stream that decompresses to the concatenation of
their contents. So this is a byte copy, not a decompress/recompress cycle.
"""

import logging
import os
import os.path

from redun import task, File
from redun_psij import Job1Spec, JobContext, run_job_1

from agr.gbs_prism.merge_policy import lanes_to_merge
from agr.seq.mgi.barcode_stat import parse_barcode_stat

logger = logging.getLogger(__name__)

MERGE_FASTQ_TOOL_NAME = "merge_fastq"


class MergeFastqError(Exception):
    pass


def library_read_counts(
    barcode_stats: dict[int, str],
) -> dict[str, dict[int, int]]:
    """`library -> lane -> reads`, from each lane's `BarcodeStat.txt`.

    splitBarcode's "sample" is the GBS library here - Tassel3 does the within-library
    barcode demultiplexing later - so its per-sample `Total` column is exactly the
    per-library read count the merge policy needs, with no fastq read.
    """
    counts: dict[str, dict[int, int]] = {}
    for lane, stat_path in barcode_stats.items():
        samples, _ = parse_barcode_stat(stat_path)
        for library, _correct, _corrected, total, _percent in samples:
            counts.setdefault(library, {})[lane] = total
    return counts


def _merge_job_spec(
    library: str,
    in_paths: list[str],
    out_path: str,
    job_context: JobContext,
) -> Job1Spec:
    """`cat` the lane fastqs, with psij redirecting stdout straight into out_path.

    Using stdout redirection rather than a shell means no quoting and no `sh -c`.
    """
    return Job1Spec(
        tool=MERGE_FASTQ_TOOL_NAME,
        args=["cat"] + in_paths,
        stdout_path=out_path,
        stderr_path="%s.stderr" % out_path,
        custom_attributes=job_context.custom_attributes,
        expected_path=out_path,
    )


@task()
def merge_library_fastq(
    library: str,
    expected_lanes: list[int],
    lane_fastqs: dict[int, str],
    read_counts: dict[int, int],
    out_path: str,
    job_context: JobContext,
) -> File:
    """Merge one library's lanes into `out_path`.

    `out_path` must satisfy gquery's contract - basename beginning with the library
    name and ending `.fastq.gz`, alone in its directory. `SeqPaths.merged_fastq`
    builds it; see the note there.
    """
    in_paths = lanes_to_merge(library, expected_lanes, lane_fastqs, read_counts)

    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)

    logger.info(
        "merging %d lane fastqs for %s into %s", len(in_paths), library, out_path
    )
    return run_job_1(
        _merge_job_spec(
            library=library,
            in_paths=in_paths,
            out_path=out_path,
            job_context=job_context.with_sub(library),
        )
    )


@task()
def merge_all_libraries(
    demultiplexed: dict[int, list[File]],
    barcode_stats: dict[int, File],
    lanes_by_library: dict[str, list[int]],
    merged_paths: dict[str, str],
    job_context: JobContext,
) -> dict[str, File]:
    """Merge every library, one job each.

    Takes splitBarcode's per-lane output as a plain dict: redun resolves task
    arguments before the body runs, so the per-library inversion below sees real
    paths rather than expressions.
    """
    by_library = lane_fastqs_by_library(demultiplexed)
    read_counts = library_read_counts(
        {lane: stat_file.path for lane, stat_file in barcode_stats.items()}
    )

    if unexpected := sorted(set(by_library) - set(lanes_by_library)):
        raise MergeFastqError(
            "splitBarcode produced fastqs for libraries the sample sheet does not "
            "list: %s" % ", ".join(unexpected)
        )

    return {
        library: merge_library_fastq(
            library=library,
            expected_lanes=lanes,
            lane_fastqs=by_library.get(library, {}),
            read_counts=read_counts.get(library, {}),
            out_path=merged_paths[library],
            job_context=job_context,
        )
        for library, lanes in lanes_by_library.items()
    }


def lane_fastqs_by_library(
    demultiplexed: dict[int, list[File]],
) -> dict[str, dict[int, str]]:
    """Invert splitBarcode's per-lane output into per-library, per-lane paths.

    splitBarcode names its output `<run>_<lane>_<sample>.fq.gz`, so the library is
    the segment after the lane label. Parsed from the right, because a run name may
    itself contain underscores even though MGI's does not.
    """
    by_library: dict[str, dict[int, str]] = {}
    for lane, fastq_files in demultiplexed.items():
        for fastq_file in fastq_files:
            basename = os.path.basename(fastq_file.path)
            library = basename.removesuffix(".fq.gz").rsplit("_", 1)[-1]
            if not library:
                raise MergeFastqError(
                    "cannot work out which library %s belongs to" % fastq_file.path
                )
            by_library.setdefault(library, {})[lane] = fastq_file.path
    return by_library
