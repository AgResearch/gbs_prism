import pytest

from agr.util.table import select, TableError


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
