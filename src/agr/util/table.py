from collections.abc import Iterator


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
