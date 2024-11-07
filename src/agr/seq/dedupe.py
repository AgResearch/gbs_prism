import logging
import subprocess

logger = logging.getLogger(__name__)


def dedupe(
    in_path: str,
    out_path: str,
    tmp_dir: str,
    jvm_args: list[str] = ["-Xmx80g"],
    clumpify_args: list[str] = ["dedupe", "optical", "dupedist=15000", "subs=0"],
):
    stdout_path = "%s.stdout" % out_path
    stderr_path = "%s.stderr" % out_path
    with open(stdout_path, "w") as stdout_f:
        with open(stderr_path, "w") as stderr_f:
            _ = subprocess.run(
                ["clumpify.sh"]
                + jvm_args
                + clumpify_args
                + [
                    "tmpdir=%s" % tmp_dir,
                    "in=%s" % in_path,
                    "out=%s" % out_path,
                ],
                check=True,
                stdout=stdout_f,
                stderr=stderr_f,
            )
