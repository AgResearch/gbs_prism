from typing import Any, Iterator, Generator


def map_columns(
    in_headings: list[str], out_headings: list[str], rows: Iterator[list[Any]]
) -> Generator[list[Any], None, None]:
    out_indices = [in_headings.index(heading) for heading in out_headings]
    for row in rows:
        yield [row[i] for i in out_indices]
