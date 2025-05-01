from collections.abc import Iterator
from dataclasses import dataclass


class TableError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


def select(
    columns: list[str], header: list[str], rows: Iterator[list[str]]
) -> Iterator[list[str]]:
    """
    Select just the desired columns from each row, including a header row in the output.
    """
    try:
        indexes = [header.index(column) for column in columns]
    except ValueError as e:
        raise TableError("unknown column: %s" % str(e))
    yield columns
    i = 0
    for row in rows:
        i += 1
        try:
            yield [row[index] for index in indexes]
        except IndexError as e:
            raise TableError("short row %d: %s" % (i, str(e)))


@dataclass
class JoinSpec:
    header: list[str]
    key0_index: int
    indexes0: list[int]
    key1_index: int
    indexes1: list[int]
    default1: list[str]


def join_spec(
    key0_name: str,
    header0: list[str],
    columns0: dict[str, str],  # supports renaming
    key1_name: str,
    header1: list[str],
    columns1: dict[str, str],  # supports renaming
    default1: list[str],
):
    if len(columns1) != len(default1):
        raise TableError("columns/default length mismatch")
    try:
        indexes0 = [header0.index(column) for column in columns0]
        indexes1 = [header1.index(column) for column in columns1]
    except ValueError as e:
        raise TableError("unknown column: %s" % str(e))
    try:
        key0_index = header0.index(key0_name)
        key1_index = header1.index(key1_name)
    except ValueError as e:
        raise TableError("unknown column: %s" % str(e))
    return JoinSpec(
        header=[columns0[header0[i]] for i in indexes0]
        + [columns1[header1[i]] for i in indexes1],
        key0_index=key0_index,
        indexes0=indexes0,
        key1_index=key1_index,
        indexes1=indexes1,
        default1=default1,
    )


def join(
    spec: JoinSpec,
    rows0: Iterator[list[str]],
    rows1: Iterator[list[str]],
) -> Iterator[list[str]]:
    yield spec.header
    rows1_by_key = {row[spec.key1_index]: row for row in rows1}
    for row0 in rows0:
        row1 = rows1_by_key.get(row0[spec.key0_index])
        joined0 = [row0[index] for index in spec.indexes0]
        joined1 = (
            [row1[index] for index in spec.indexes1]
            if row1 is not None
            else spec.default1
        )
        yield joined0 + joined1
