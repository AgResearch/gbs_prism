from dataclasses import dataclass
from jinja2 import Environment, PackageLoader, select_autoescape
from typing import Literal, Optional

# HTML reports with multiple columns and multiple sections, defined in a Jinja template.
# The list of columns is defined per chapter.
# Sections may be rendered with or without row names.


@dataclass(kw_only=True)
class Row:
    """The target per column."""

    name: Optional[str] = None
    description: Optional[str] = None
    by_column: dict[
        str, Optional[str]
    ]  # for inline kind this is the file content not the path


@dataclass(kw_only=True)
class Section:
    """A section contains multiple rows all of the same kind."""

    name: Optional[str] = None
    named_rows: bool = False
    kind: Literal["image", "link", "inline"]
    rows: list[Row]


@dataclass(kw_only=True)
class Chapter:
    """A chapter is a list of sections for the same columns."""

    name: Optional[str] = None
    columns: list[str]
    sections: list[Section]


@dataclass(kw_only=True)
class Report:
    name: str
    chapters: list[Chapter]


def render_report(report: Report, out_path: str, template="report.html.jinja"):
    env = Environment(loader=PackageLoader("agr.util"), autoescape=select_autoescape())
    template = env.get_template(template)
    with open(out_path, "w") as out_f:
        _ = out_f.write(template.render(report=report))
