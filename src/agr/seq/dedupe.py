import logging
import os.path
import subprocess

logger = logging.getLogger(__name__)


def dedupe(
    in_path: str,
    out_path: str,
    tmp_dir: str,
    jvm_args: list[str] = ["-Xmx160g"],
    clumpify_args: list[str] = ["dedupe", "optical", "dupedist=15000", "subs=0"],
):
    # we run in the out_dir because clumpify is in the habit of dumping hs_err_pid1234.log files.
    out_dir = os.path.dirname(out_path)
    stdout_path = "%s.stdout" % out_path
    stderr_path = "%s.stderr" % out_path
    with open(stdout_path, "w") as stdout_f:
        with open(stderr_path, "w") as stderr_f:
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
            _ = subprocess.run(
                cmd,
                check=True,
                stdout=stdout_f,
                stderr=stderr_f,
                cwd=out_dir,
            )
