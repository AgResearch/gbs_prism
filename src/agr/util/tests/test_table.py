import pytest

from agr.util.table import select, join_spec, join, TableError


def test_select_1():
    actual = list(
        select(
            ["C", "B"],
            ["A", "B", "C"],
            iter([["a1", "b1", "c1"], ["a2", "b2", "c2"], ["a3", "b3", "c3"]]),
        )
    )
    assert actual == [["C", "B"], ["c1", "b1"], ["c2", "b2"], ["c3", "b3"]]


def test_select_unknown_column_raises():
    with pytest.raises(TableError) as excinfo:
        _ = list(
            select(
                ["C", "D"],
                ["A", "B", "C"],
                iter([["a1", "b1", "c1"], ["a2", "b2", "c2"], ["a3", "b3", "c3"]]),
            )
        )
    assert str(excinfo.value) == "unknown column: 'D' is not in list"


def test_select_short_row_raises():
    with pytest.raises(TableError) as excinfo:
        _ = list(
            select(
                ["C", "B"],
                ["A", "B", "C"],
                iter([["a1", "b1", "c1"], ["a2", "b2"], ["a3", "b3", "c3"]]),
            )
        )
    assert str(excinfo.value) == "short row 2: list index out of range"


def test_join_1():
    t0 = [
        ["A0", "B0", "C0"],
        ["a1", "b1", "c1"],
        ["a2", "b2", "c2"],
        ["a3", "b3", "c3"],
        ["a4", "b4", "c4"],
    ]
    t1 = [
        ["A1", "D1", "E1", "F1"],
        ["a3", "d3", "e3", "f3"],
        ["a2", "d2", "e2", "f2"],
        ["a5", "d5", "e5", "f5"],
        ["a1", "d1", "e1", "f1"],
    ]
    spec = join_spec(
        "A0",
        t0[0],
        {"A0": "A", "B0": "B"},
        "A1",
        t1[0],
        {"D1": "D", "E1": "E"},
        ["", ""],
    )
    actual = list(join(spec, iter(t0[1:]), iter(t1[1:])))
    assert actual == [
        [
            "A",
            "B",
            "D",
            "E",
        ],
        ["a1", "b1", "d1", "e1"],
        ["a2", "b2", "d2", "e2"],
        ["a3", "b3", "d3", "e3"],
        ["a4", "b4", "", ""],
    ]
