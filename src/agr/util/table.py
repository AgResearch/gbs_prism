from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Optional, Callable


class TableError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


def select(
    columns: list[str], header: list[str], rows: Iterator[list[Any]]
) -> Iterator[list[Any]]:
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
class JoineeSpec:
    key_index: int
    indexes: list[int]
    default: list[str]


@dataclass
class JoinSpec:
    header: list[str]
    joinee_specs: list[JoineeSpec]


@dataclass
class Joinee:
    key_name: str
    header: list[str]
    columns: list[str]
    default: Optional[list[str]] = None
    renames: dict[str, str] = field(default_factory=dict)


def join_spec(
    joinees: list[Joinee],
) -> JoinSpec:
    header = []
    joinee_specs = []
    for joinee in joinees:
        try:
            indexes = [joinee.header.index(column) for column in joinee.columns]
            key_index = joinee.header.index(joinee.key_name)
        except ValueError as e:
            raise TableError("unknown column: %s" % str(e))
        header += [joinee.renames.get(column, column) for column in joinee.columns]

        if joinee.default is not None and len(joinee.default) != len(joinee.columns):
            raise TableError("columns/default length mismatch")
        joinee_default = (
            joinee.default if joinee.default is not None else [""] * len(joinee.columns)
        )

        joinee_specs.append(
            JoineeSpec(key_index=key_index, indexes=indexes, default=joinee_default)
        )

    if len(sorted(header)) != len(header):
        raise TableError("duplicate column in %s" % " ".join(header))

    return JoinSpec(header=header, joinee_specs=joinee_specs)


def left_join(
    spec: JoinSpec,
    joinee_rows: list[Iterator[list[Any]]],
) -> Iterator[list[Any]]:
    if len(spec.joinee_specs) != len(joinee_rows):
        raise TableError(
            "spec len %d != joinee_rows len %d"
            % (len(spec.joinee_specs), len(joinee_rows))
        )

    yield spec.header

    rows_by_keys = []  # not primary
    for i in range(1, len(spec.joinee_specs)):
        rows_by_keys.append(
            {row[spec.joinee_specs[i].key_index]: row for row in joinee_rows[i]}
        )

    spec_0 = spec.joinee_specs[0]
    for row_0 in joinee_rows[0]:
        joined = [row_0[index] for index in spec_0.indexes]
        for i in range(1, len(spec.joinee_specs)):
            rows_by_key_i = rows_by_keys[i - 1]  # because didn't index zeroth joinee
            spec_i = spec.joinee_specs[i]
            row_i = rows_by_key_i.get(row_0[spec_0.key_index])
            joined += (
                [row_i[index] for index in spec_i.indexes]
                if row_i is not None
                else spec_i.default
            )
        yield joined


def split_column(
    column: str,
    new_columns: list[str],
    splitter: Callable[[Any], list[Any]],
    header: list[str],
    rows: Iterator[list[Any]],
    default: str = "",
) -> Iterator[list[Any]]:
    """
    Split a column by splitter;  values beyond the number of new_columns are discarded.
    Any shortfall is filled on the right by default.
    """
    try:
        column_index = header.index(column)
    except ValueError as e:
        raise TableError("unknown column: %s" % str(e))

    n_expected = len(new_columns)

    def splice(row: list[str], i: int, new_values: list[str]) -> list[str]:
        if i == 0:
            return new_values + row[1:]
        elif i == len(row) - 1:
            return row[:-1] + new_values
        else:
            return row[:i] + new_values + row[i + 1 :]

    yield splice(header, column_index, new_columns)
    for row in rows:
        if column_index >= len(row):
            yield row
        else:
            new_values = splitter(row[column_index])
            if len(new_values) < n_expected:
                # shortfall, so pad with repeated default
                new_values += [default] * (n_expected - len(new_values))
            elif len(new_values) > n_expected:
                new_values = new_values[:n_expected]
            yield splice(row, column_index, new_values)
