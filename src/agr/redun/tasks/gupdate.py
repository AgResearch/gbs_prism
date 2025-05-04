import csv
import shutil
from redun import task, File
from typing import Optional

from agr.gquery import GUpdate, Predicates
from agr.seq.types import Cohort
from agr.util import map_columns
from agr.util.file_hash import write_file_legible_hash


@task()
def import_gbs_read_tag_counts(run: str, collated_tag_count: File) -> File:
    imported_marker_path = "%s.imported.md5" % collated_tag_count.path

    GUpdate(
        explain=True,
        task="lab_report",
        predicates=Predicates(
            name="import_gbs_read_tag_counts", file=collated_tag_count.path
        ),
        items=[run],
    ).run()

    # write a file containing a hash of what we imported for redun caching
    write_file_legible_hash(collated_tag_count.path, imported_marker_path)
    return File(imported_marker_path)


@task()
def create_cohort_gbs_kgd_stats_import(
    run: str, cohort_name: str, kgd_stats_csv: Optional[File]
) -> Optional[File]:
    """Create the import file in the correct format for a single cohort, but don't actually import."""
    if kgd_stats_csv is None:
        return None
    else:
        import_path = "%s.import-gbs.tsv" % kgd_stats_csv.path.removesuffix(".csv")

        with open(kgd_stats_csv.path, "r") as kgd_stats_f:
            kgd_stats = csv.reader(kgd_stats_f)
            kgd_stats_header = next(kgd_stats)
            with open(import_path, "w") as import_f:
                # Map the columns into the required format as defined by
                # gquery/sequencing/illumina.py where the name predicate is import_gbs_kgd_stats
                for row in map_columns(
                    kgd_stats_header, ["seqID", "callrate", "sampdepth"], kgd_stats
                ):
                    _ = import_f.write("%s\n" % "\t".join([run, cohort_name] + row))

        return File(import_path)


@task()
def import_gbs_kgd_stats(
    run: str, cohort_imports: list[Optional[File]], out_path: str
) -> File:
    """Import all KGD stats import files in one go, since importing individual files
    seems to result in database deadlock.

    Any cohorts for which KGD failed result in None in place of the import file, and we simply omit these.
    """

    # concatenate all import files
    with open(out_path, "w") as out_f:
        for cohort_import in cohort_imports:
            if cohort_import is not None:
                with open(cohort_import.path, "r") as cohort_import_f:
                    shutil.copyfileobj(cohort_import_f, out_f)

    GUpdate(
        explain=True,
        task="lab_report",
        predicates=Predicates(name="import_gbs_kgd_stats", file=out_path),
        items=[run],
    ).run()

    return File(out_path)


@task()
def import_gbs_kgd_cohort_stats(
    run: str, cohort: Cohort, kgd_stdout: Optional[File]
) -> Optional[File]:
    if kgd_stdout is None:
        return None
    else:
        GUpdate(
            explain=True,
            task="lab_report",
            predicates=Predicates(
                name="import_gbs_kgd_cohort_stats",
                file=kgd_stdout.path,
                libraryname=cohort.libname,
                qc_cohort=cohort.qc_cohort,
                gbs_cohort=cohort.gbs_cohort,
                enzyme=cohort.enzyme,
            ),
            items=[run],
        ).run()

        out_path = "%s.imported" % kgd_stdout.path
        with open(out_path, "w") as out_f:
            _ = out_f.write("imported hash %s\n" % kgd_stdout.hash)
        return File(out_path)
