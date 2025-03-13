import glob
import logging
import os
import os.path

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)


def _base_path(out_path: str) -> str:
    return out_path.removesuffix(".gz").removesuffix(".fastq")


DEDUPE_TOOL_NAME = "dedupe"


def dedupe_job_spec(
    in_path: str,
    out_path: str,
    tmp_dir: str,
    jvm_args: list[str] = [],
    clumpify_args: list[str] = ["dedupe", "optical", "dupedist=15000", "subs=0"],
) -> cluster.Job1Spec:
    # we run in the out_dir because clumpify is in the habit of dumping hs_err_pid1234.log files.
    out_dir = os.path.dirname(out_path)
    base_path = _base_path(out_path)
    log_path = f"{base_path}.clumpfy.log"
    return cluster.Job1Spec(
        tool=DEDUPE_TOOL_NAME,
        args=["clumpify.sh"]
        + jvm_args
        + clumpify_args
        + [
            "tmpdir=%s" % tmp_dir,
            "in=%s" % in_path,
            "out=%s" % out_path,
        ],
        stdout_path=log_path,
        stderr_path=log_path,
        cwd=out_dir,
        expected_path=out_path,
    )


def remove_dedupe_turds(out_path: str):
    # remove any turds dropped by clumpify, because these break keyfile_table_import
    # filenames are like SQ5051_S1_L001_R1_001_clumpify_p1_temp0_20b4208f2aae2ca8.fastq.gz
    base_path = _base_path(out_path)
    for turd in glob.glob(f"{base_path}_clumpify_*"):
        try:
            os.remove(turd)
        except FileNotFoundError:
            pass
