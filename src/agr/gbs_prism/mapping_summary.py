"""BWA mapping % summary, restricted to the reference genome(s) indicated by the keyfile.

Each cohort is mapped against every reference in its keyfile rows, which includes
sheep because negative controls are keyed as SHEEP.  The summary here keeps only the
references the keyfile indicates for the cohort (see
`agr.gbs_prism.gbs_target_spec.indicated_references`).
"""

import csv
import os.path
import re
from dataclasses import dataclass
from typing import Optional

NONE_INDICATED = "(none indicated)"

_HEADER = ["cohort", "sample", "reference", "reads", "map_pct", "map_std"]


@dataclass(frozen=True)
class FlagstatCounts:
    total: int
    mapped: int


def parse_flagstat(path: str) -> FlagstatCounts:
    """Total and mapped read counts from `samtools flagstat` output."""
    total = 0
    mapped = 0
    with open(path, "r") as f:
        for record in f:
            tokens = re.split(r"\s+", record.strip())
            if len(tokens) >= 5:
                if (tokens[3], tokens[4]) == ("in", "total"):
                    total = int(tokens[0])
                elif tokens[3] == "mapped":
                    # the first mapped line, not "primary mapped"
                    mapped = int(tokens[0])
                    break
    return FlagstatCounts(total=total, mapped=mapped)


def mapping_pct_and_std(counts: FlagstatCounts) -> tuple[float, float]:
    """Mapping % and its binomial standard deviation, also in %."""
    if counts.total <= 0:
        return (0.0, 0.0)
    p = counts.mapped / counts.total
    std = (p * (1 - p) / counts.total) ** 0.5
    return (p * 100.0, std * 100.0)


def reference_for_stats_file(path: str, ref_names: list[str]) -> Optional[str]:
    """Which of `ref_names` a bwa stats file is for, from its `.bwa.<ref>.` token.

    The longest match wins, in case one reference name is a prefix of another.
    """
    basename = os.path.basename(path)
    matches = [ref for ref in ref_names if (".bwa.%s." % ref) in basename]
    return max(matches, key=len) if matches else None


def sample_for_stats_file(path: str) -> str:
    """The sample (library fastq) name, being the stats file basename before `.fastq`."""
    return os.path.basename(path).split(".fastq", 1)[0]


@dataclass(frozen=True)
class MappingRow:
    cohort: str
    sample: str
    reference: str
    reads: Optional[int]
    map_pct: Optional[float]
    map_std: Optional[float]


def indicated_mapping_rows(
    stats_by_cohort: dict[str, list[str]],
    refs_by_cohort: dict[str, list[str]],
    indicated_by_cohort: dict[str, list[str]],
) -> list[MappingRow]:
    """Mapping rows for the indicated references only, sorted by cohort then reference.

    A cohort with no indicated reference gets a single `NONE_INDICATED` row with no
    numbers, so that it remains visible in the report.
    """
    rows = []
    for cohort in sorted(set(stats_by_cohort) | set(indicated_by_cohort)):
        indicated = set(indicated_by_cohort.get(cohort, []))
        if not indicated:
            rows.append(
                MappingRow(
                    cohort=cohort,
                    sample="",
                    reference=NONE_INDICATED,
                    reads=None,
                    map_pct=None,
                    map_std=None,
                )
            )
            continue
        ref_names = refs_by_cohort.get(cohort, [])
        for stats_path in stats_by_cohort.get(cohort, []):
            reference = reference_for_stats_file(stats_path, ref_names)
            if reference is None or reference not in indicated:
                continue
            counts = parse_flagstat(stats_path)
            map_pct, map_std = mapping_pct_and_std(counts)
            rows.append(
                MappingRow(
                    cohort=cohort,
                    sample=sample_for_stats_file(stats_path),
                    reference=reference,
                    reads=counts.total,
                    map_pct=map_pct,
                    map_std=map_std,
                )
            )
    return sorted(rows, key=lambda row: (row.cohort, row.reference, row.sample))


def _str_or_empty(value) -> str:
    return "" if value is None else str(value)


def write_mapping_summary(rows: list[MappingRow], path: str):
    with open(path, "w", newline="") as out_f:
        writer = csv.writer(out_f, delimiter="\t", lineterminator="\n")
        writer.writerow(_HEADER)
        for row in rows:
            writer.writerow(
                [
                    row.cohort,
                    row.sample,
                    row.reference,
                    _str_or_empty(row.reads),
                    _str_or_empty(row.map_pct),
                    _str_or_empty(row.map_std),
                ]
            )


def read_mapping_summary(path: str) -> list[MappingRow]:
    def _opt(value: str, conv):
        return conv(value) if value != "" else None

    with open(path, "r", newline="") as in_f:
        reader = csv.DictReader(in_f, delimiter="\t")
        return [
            MappingRow(
                cohort=rec["cohort"],
                sample=rec["sample"],
                reference=rec["reference"],
                reads=_opt(rec["reads"], int),
                map_pct=_opt(rec["map_pct"], float),
                map_std=_opt(rec["map_std"], float),
            )
            for rec in reader
        ]
