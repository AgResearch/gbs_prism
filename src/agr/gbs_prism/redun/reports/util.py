import os.path
from redun import File
from typing import Optional

from agr.util.report import (
    Row,
    Image,
    Link,
)


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
