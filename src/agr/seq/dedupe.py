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
    log_path = "%s.log" % out_path.removesuffix(".fastq.gz")
    with open(log_path, "w") as log_f:
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
            stdout=log_f,
            stderr=log_f,
        )
