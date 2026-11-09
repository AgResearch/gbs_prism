import os.path
import shutil

import pytest

from agr.gbs_prism.gbs_target_spec import (
    GbsTargetSpec,
    indicated_references,
    parse_control_reference_rows,
)
from agr.gbs_prism.mapping_summary import (
    NONE_INDICATED,
    FlagstatCounts,
    indicated_mapping_rows,
    mapping_pct_and_std,
    parse_flagstat,
    read_mapping_summary,
    reference_for_stats_file,
    write_mapping_summary,
)
from agr.gbs_prism.redun.reports.util import mapping_table
from agr.util.report import Chapter, Report, Row, Section, render_report

HERE = os.path.dirname(__file__)

# real `samtools flagstat` (1.21) output, DL100022100 SQ5636 vs goat
FLAGSTAT = os.path.join(HERE, "flagstat-samtools-1.21.stats")

GOAT = "capra_hircus_ncbi_PRJNA290100.fasta"
SHEEP = "sheep.v3.0.14th.final.fa"
GOAT_PATH = "/dataset/datacache/scratch/ncbi/indexes/bwa/" + GOAT
SHEEP_PATH = "/dataset/OARv3.0/active/current_version/" + SHEEP

STATS_STEM = "SQ5636_DL100022100.fastq.gz.fastq.m150000.trimmed.fastq.bwa"


def test_parse_flagstat_real_output():
    # "primary mapped" follows "mapped" and must not override it
    assert parse_flagstat(FLAGSTAT) == FlagstatCounts(total=149776, mapped=135204)


def test_mapping_pct_and_std():
    pct, std = mapping_pct_and_std(FlagstatCounts(total=149776, mapped=135204))
    assert pct == pytest.approx(90.2708, abs=1e-4)
    assert std == pytest.approx(0.07657, abs=1e-4)
    assert mapping_pct_and_std(FlagstatCounts(total=0, mapped=0)) == (0.0, 0.0)


def test_reference_for_stats_file():
    refs = [GOAT, SHEEP]
    assert reference_for_stats_file(f"/x/{STATS_STEM}.{SHEEP}.B10.stats", refs) == SHEEP
    assert reference_for_stats_file(f"/x/{STATS_STEM}.{GOAT}.B10.stats", refs) == GOAT
    assert reference_for_stats_file(f"/x/{STATS_STEM}.other.fa.B10.stats", refs) is None


def test_reference_for_stats_file_prefers_longest():
    refs = ["ref.fa", "ref.fa.v2"]
    path = f"{STATS_STEM}.ref.fa.v2.B10.stats"
    assert reference_for_stats_file(path, refs) == "ref.fa.v2"


def test_parse_control_reference_rows():
    lines = [
        f"NEGATIVE\t{SHEEP_PATH}\n",
        f"\t{GOAT_PATH}\n",
        f"POSITIVE\t{GOAT_PATH}\n",
        "POSITIVE\t\n",
        "\n",
    ]
    assert parse_control_reference_rows(lines) == [
        ("NEGATIVE", SHEEP_PATH),
        ("", GOAT_PATH),
        ("POSITIVE", GOAT_PATH),
        ("POSITIVE", ""),
    ]


def test_indicated_references_excludes_negative_controls():
    rows = [("NEGATIVE", SHEEP_PATH), ("", GOAT_PATH), ("POSITIVE", GOAT_PATH)]
    assert indicated_references(rows) == [GOAT]


def test_indicated_references_negative_is_case_insensitive():
    assert indicated_references([("negative", SHEEP_PATH), ("", GOAT_PATH)]) == [GOAT]


def test_indicated_references_sheep_cohort():
    rows = [("NEGATIVE", SHEEP_PATH), ("", SHEEP_PATH), ("POSITIVE", SHEEP_PATH)]
    assert indicated_references(rows) == [SHEEP]


def test_indicated_references_none():
    # microbes cohorts have no reference at all
    assert indicated_references([("POSITIVE", "")]) == []
    assert indicated_references([("NEGATIVE", SHEEP_PATH)]) == []
    assert indicated_references([]) == []


def test_target_spec_without_indicated_references_still_loads():
    spec = GbsTargetSpec.model_validate_json('{"libraries": {}}')
    assert spec.indicated_references == {}


@pytest.fixture
def goat_cohort_stats(tmp_path):
    goat = tmp_path / f"{STATS_STEM}.{GOAT}.B10.stats"
    sheep = tmp_path / f"{STATS_STEM}.{SHEEP}.B10.stats"
    shutil.copy(FLAGSTAT, goat)
    shutil.copy(FLAGSTAT, sheep)
    return [str(sheep), str(goat)]


def test_indicated_mapping_rows(goat_cohort_stats):
    goat_cohort = "SQ5636.all.goat.PstI"
    microbes_cohort = "SQ5227.all.microbes.PstI"
    rows = indicated_mapping_rows(
        stats_by_cohort={goat_cohort: goat_cohort_stats, microbes_cohort: []},
        refs_by_cohort={goat_cohort: [GOAT, SHEEP], microbes_cohort: []},
        indicated_by_cohort={goat_cohort: [GOAT], microbes_cohort: []},
    )
    assert [(row.cohort, row.reference) for row in rows] == [
        (microbes_cohort, NONE_INDICATED),
        (goat_cohort, GOAT),
    ]
    microbes, goat = rows
    assert microbes.reads is None and microbes.map_pct is None
    assert goat.sample == "SQ5636_DL100022100"
    assert goat.reads == 149776
    assert goat.map_pct == pytest.approx(90.2708, abs=1e-4)


def test_cohort_missing_from_indicated_is_none_indicated(goat_cohort_stats):
    # e.g. a target-spec.json written before indicated_references existed
    rows = indicated_mapping_rows(
        stats_by_cohort={"c": goat_cohort_stats},
        refs_by_cohort={"c": [GOAT, SHEEP]},
        indicated_by_cohort={},
    )
    assert [row.reference for row in rows] == [NONE_INDICATED]


def test_mapping_summary_round_trip(goat_cohort_stats, tmp_path):
    rows = indicated_mapping_rows(
        stats_by_cohort={"a": goat_cohort_stats, "b": []},
        refs_by_cohort={"a": [GOAT, SHEEP]},
        indicated_by_cohort={"a": [GOAT, SHEEP], "b": []},
    )
    path = str(tmp_path / "indicated_mapping_summary.txt")
    write_mapping_summary(rows, path)
    assert read_mapping_summary(path) == rows


def test_mapping_table_renders(goat_cohort_stats, tmp_path):
    rows = indicated_mapping_rows(
        stats_by_cohort={"SQ5636.all.goat.PstI": goat_cohort_stats},
        refs_by_cohort={"SQ5636.all.goat.PstI": [GOAT, SHEEP]},
        indicated_by_cohort={"SQ5636.all.goat.PstI": [GOAT], "microbes": []},
    )
    out_path = str(tmp_path / "report.html")
    render_report(
        Report(
            name="test",
            chapters=[
                Chapter(
                    sections=[
                        Section(
                            named_rows=True,
                            rows=[Row(name="mapping", target=mapping_table(rows))],
                        )
                    ]
                )
            ],
        ),
        out_path,
    )
    with open(out_path) as f:
        html = f.read()
    assert "<th>Mapped %</th>" in html
    assert "<td>90.27</td>" in html
    assert "<td>149,776</td>" in html
    assert f"<td>{GOAT}</td>" in html
    assert SHEEP not in html
    assert f"<td>{NONE_INDICATED}</td>" in html
