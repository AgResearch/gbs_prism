"""This module replaces qc_sampleids with sampleid using GQuery derived sed scripts"""

import logging
import os.path
from redun import task, File
from typing import Optional

from agr.redun import one_forall, one_foreach
from agr.util.path import get_file_hash_times
from agr.util.subprocess import run_catching_stderr
from agr.gquery import GQuery, Predicates

logger = logging.getLogger(__name__)


@task(cache=False)
def get_unblind_script(
    out_dir: str,
    flowcell_id: str,
    enzyme: str,
    gbs_cohort: str,
    library: str,
    keyfile: File,
) -> File:
    """
    Get the unblind script for cohort using GQuery.
    """

    # The keyfile is just a trigger, so this task reruns if the keyfile changes
    _ = keyfile

    out_path = os.path.join(out_dir, f"{library}.all.{gbs_cohort}.{enzyme}.unblind.sed")
    previous = get_file_hash_times(out_path)

    with open(out_path, "w") as out_f:
        GQuery(
            task="gbs_keyfile",
            badge_type="library",
            predicates=Predicates(
                flowcell=flowcell_id,
                enzyme=enzyme,
                gbs_cohort=gbs_cohort,
                unblinding=True,
                columns="qc_sampleid,sample",
                noheading=True,
            ),
            items=[library],
            outfile=out_f,
        ).run()

    if previous is not None:
        latest = get_file_hash_times(out_path)
        assert latest is not None
        if latest.hash == previous.hash:
            # file is the same, but redun won't think so unless we reset the mtime
            os.utime(out_path, ns=(previous.atime_ns, previous.mtime_ns))

    return File(out_path)


@task()
def unblind_one(
    blinded_file: File,
    unblind_script: File,
    out_dir: str,
) -> File:
    """
    Unblind a single result file.
    """

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(blinded_file.path))

    with open(out_path, "w") as out_f:
        run_catching_stderr(
            ["sed", "-f", unblind_script.path, blinded_file.path],
            stdout=out_f,
            check=True,
        )
    return File(out_path)


@task()
def unblind_optional(
    blinded_file: Optional[File],
    unblind_script: File,
    out_dir: str,
) -> Optional[File]:
    return (
        unblind_one(blinded_file, unblind_script, out_dir)
        if blinded_file is not None
        else None
    )


@task()
def unblind_all(
    blinded_files: list[File],
    unblind_script: File,
    out_dir: str,
) -> list[File]:
    """
    Unblind a list of result files.
    """
    return one_forall(
        task=unblind_one,
        items=blinded_files,
        unblind_script=unblind_script,
        out_dir=out_dir,
    )


@task()
def unblind_each(
    blinded_files: dict[str, File],
    unblind_script: File,
    out_dir: str,
) -> dict[str, File]:
    """
    Unblind a list of result files.
    """
    return one_foreach(
        task=unblind_one,
        items=blinded_files,
        unblind_script=unblind_script,
        out_dir=out_dir,
    )
