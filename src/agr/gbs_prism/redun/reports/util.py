import os.path
from redun import File
from typing import Optional

from agr.util.report import (
    Row,
    Image,
    Link,
    Table,
)
from agr.gbs_prism.mapping_summary import MappingRow, read_mapping_summary


def image_or_none(
    file: Optional[File],
    relbase: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Optional[Image]:
    return (
        Image(os.path.relpath(file.path, relbase), width=width, height=height)
        if file is not None and os.path.exists(file.path)
        else None
    )


def link_or_none(file: Optional[File], relbase: str) -> Optional[Link]:
    return (
        Link(os.path.relpath(file.path, relbase))
        if file is not None and os.path.exists(file.path)
        else None
    )


def row_for_link(file: File, relbase: str) -> Row:
    return Row(name=os.path.basename(file.path), target=link_or_none(file, relbase))


def _fmt_or_blank(value, fmt: str) -> str:
    return "" if value is None else fmt.format(value)


def mapping_table(rows: list[MappingRow]) -> Table:
    return Table(
        header=["Cohort", "Sample", "Reference", "Reads sampled", "Mapped %", "SD %"],
        rows=[
            [
                row.cohort,
                row.sample,
                row.reference,
                _fmt_or_blank(row.reads, "{:,}"),
                _fmt_or_blank(row.map_pct, "{:.2f}"),
                _fmt_or_blank(row.map_std, "{:.2f}"),
            ]
            for row in rows
        ],
    )


def mapping_table_or_none(file: Optional[File]) -> Optional[Table]:
    return (
        mapping_table(read_mapping_summary(file.path))
        if file is not None and os.path.exists(file.path)
        else None
    )
