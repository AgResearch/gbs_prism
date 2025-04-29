from dataclasses import dataclass
from jinja2 import Environment, PackageLoader, select_autoescape
from typing import Optional

# HTML reports with multiple columns and multiple sections, defined in a Jinja template.
# The list of columns is defined per chapter.
# Sections may be rendered with or without row names.


@dataclass
class Image:
    url: str


@dataclass
class Link:
    url: str


@dataclass
class Inline:
    content: str


Target = Image | Link | Inline


@dataclass(kw_only=True)
class Row:
    """
    The target, or target per column.

    In chapters with columns, the values for each row are taken from `by_column`,
    otherwise the single value for the row is taken from `target`.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    target: Optional[Target] = None
    by_column: Optional[dict[str, Optional[Target]]] = None


@dataclass(kw_only=True)
class Section:
    """A section contains multiple rows with an optional heading."""

    name: Optional[str] = None
    named_rows: bool = False
    rows: list[Row]


@dataclass(kw_only=True)
class Chapter:
    """A chapter is a list of sections for the same columns (or single column by default)."""

    name: Optional[str] = None
    columns: Optional[list[str]] = None
    sections: list[Section]


@dataclass(kw_only=True)
class Report:
    name: str
    chapters: list[Chapter]


def render_report(
    report: Report, out_path: str, module="agr", template="report.html.jinja"
):
    """
    Render template f"{module}/templates/{template}" using `report`.
    """
    env = Environment(loader=PackageLoader(module), autoescape=select_autoescape())

    # register extra functions and classes we want to use in the Jinja template
    env.globals.update(isinstance=isinstance, Image=Image, Link=Link, Inline=Inline)

    template = env.get_template(template)
    with open(out_path, "w") as out_f:
        _ = out_f.write(template.render(report=report))
