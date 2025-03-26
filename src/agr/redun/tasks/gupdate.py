from redun import task, File

from agr.gquery import GUpdate, Predicates
from agr.util.file_hash import write_file_legible_hash


@task()
def import_gbs_read_tag_counts(run: str, collated_tag_count: File) -> File:
    imported_marker_path = "%s.imported.md5" % collated_tag_count.path

    GUpdate(
        task="lab_report",
        predicates=Predicates(
            name="import_gbs_read_tag_counts", file=collated_tag_count.path
        ),
        items=[run],
    ).run()

    # write a file containing a hash of what we imported for redun caching
    write_file_legible_hash(collated_tag_count.path, imported_marker_path)
    return File(imported_marker_path)
