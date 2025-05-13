import os.path
from redun import task, File

from agr.gquery import GQuery
from agr.util.file_hash import file_legible_hash
from agr.util.subprocess import run_catching_stderr
from agr.seq.types import flowcell_id


@task()
def get_genophyle_export(out_path: str) -> File:
    with open(out_path, "w") as out_f:
        GQuery(
            task="get_genophyle_export",
            outfile=out_f,
        ).run()
    return File(out_path)


@task()
def import_genophyle_gbs_import_file(
    genophyle_gbs_import_file: File, log_dir: str
) -> str:
    """Import and return an import marker, which is a legible hash of the imported file content."""
    log_path = os.path.join(log_dir, "warehouse_update.log")
    with open(log_path, "w") as log_f:
        _ = run_catching_stderr(
            [
                "geno_import",
                "-H",
                "invsqlpv05",  # this means whichever genotype database we're configured to use, gah!
                "-t",
                "gbs_tab",
                genophyle_gbs_import_file.path,
            ],
            stdout=log_f,
            check=True,
        )
    return file_legible_hash(genophyle_gbs_import_file.path)


@task()
def warehouse(ready: bool, geno_import_dir: str, log_dir: str, run: str) -> str:
    _ = ready

    os.makedirs(geno_import_dir, exist_ok=True)

    genophyle_gbs_import_file = get_genophyle_export(
        out_path=os.path.join(geno_import_dir, (flowcell_id(run) + ".genophyle_gbs_import.txt"))
    )

    import_marker = import_genophyle_gbs_import_file(
        genophyle_gbs_import_file, log_dir=log_dir
    )

    return import_marker
