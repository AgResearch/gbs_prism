import pytest

from agr.util.table import select, join_spec, join, split_column, TableError


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


def test_splice_1():
    t = [
        ["A", "B", "C"],
        ["a-1", "bX1", "c*1"],
        ["a-2", "bX2", "c*2"],
        ["a-3", "bX3", "c3"],
        ["a-4", "b4", "c*4"],
    ]

    assert list(
        split_column("A", ["A1", "A2"], lambda s: s.split("-"), t[0], iter(t[1:]))
    ) == [
        ["A1", "A2", "B", "C"],
        ["a", "1", "bX1", "c*1"],
        ["a", "2", "bX2", "c*2"],
        ["a", "3", "bX3", "c3"],
        ["a", "4", "b4", "c*4"],
    ]

    assert list(
        split_column("B", ["B1", "B2"], lambda s: s.split("X"), t[0], iter(t[1:]))
    ) == [
        ["A", "B1", "B2", "C"],
        ["a-1", "b", "1", "c*1"],
        ["a-2", "b", "2", "c*2"],
        ["a-3", "b", "3", "c3"],
        ["a-4", "b4", "", "c*4"],
    ]

    assert list(
        split_column(
            "C", ["C1", "C2"], lambda s: s.split("*"), t[0], iter(t[1:]), default="oops"
        )
    ) == [
        ["A", "B", "C1", "C2"],
        ["a-1", "bX1", "c", "1"],
        ["a-2", "bX2", "c", "2"],
        ["a-3", "bX3", "c3", "oops"],
        ["a-4", "b4", "c", "4"],
    ]


def test_splice_2():
    v = [
        ["A", "B", "C"],
        ["a-1", "bX1", "c1-2-3-4"],
        ["a-2", "bX2", "c2-2"],
        ["a-3", "bX3", "c3"],
        ["a-4", "b4", "c4-2-3-4-5-6"],
    ]
    assert list(
        split_column(
            "C", ["C1", "C2", "C3", "C4"], lambda s: s.split("-"), v[0], iter(v[1:])
        )
    ) == [
        ["A", "B", "C1", "C2", "C3", "C4"],
        ["a-1", "bX1", "c1", "2", "3", "4"],
        ["a-2", "bX2", "c2", "2", "", ""],
        ["a-3", "bX3", "c3", "", "", ""],
        ["a-4", "b4", "c4", "2", "3", "4"],
    ]
