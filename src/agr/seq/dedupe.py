import glob
import logging
import os
import os.path

from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


def dedupe(
    in_path: str,
    out_path: str,
    tmp_dir: str,
    jvm_args: list[str] = [],
    clumpify_args: list[str] = ["dedupe", "optical", "dupedist=15000", "subs=0"],
):
    # we run in the out_dir because clumpify is in the habit of dumping hs_err_pid1234.log files.
    out_dir = os.path.dirname(out_path)
    base_path = out_path.removesuffix(".gz").removesuffix(".fastq")
    log_path = f"{base_path}.clumpfy.log"
    with open(log_path, "w") as log_f:
        cmd = (
            ["clumpify.sh"]
            + jvm_args
            + clumpify_args
            + [
                "tmpdir=%s" % tmp_dir,
                "in=%s" % in_path,
                "out=%s" % out_path,
            ]
        )
        logger.info(" ".join(cmd))
        try:
            _ = run_catching_stderr(
                cmd,
                check=True,
                stdout=log_f,
                stderr=log_f,
                cwd=out_dir,
            )
        finally:
            # remove any turds dropped by clumpify, because these break keyfile_table_import
            # filenames are like SQ5051_S1_L001_R1_001_clumpify_p1_temp0_20b4208f2aae2ca8.fastq.gz
            for turd in glob.glob(f"{base_path}_clumpify_*"):
                try:
                    os.remove(turd)
                except FileNotFoundError:
                    pass
