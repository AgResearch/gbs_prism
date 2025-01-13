import logging
import subprocess

from agr.util.path import remove_if_exists

logger = logging.getLogger(__name__)


def run_kmer_analysis(in_path: str, out_path: str, input_filetype: str, kmer_size: int):
    log_path = "%s.log" % out_path.removesuffix(".1")
    with open(log_path, "w") as log_f:
        remove_if_exists(out_path)
        _ = subprocess.run(
            [
                "kmer_prism",
                "--input_filetype",
                input_filetype,
                "kmer_size",
                str(kmer_size),
                "--output_filename",
                out_path,
                in_path,
            ],
            stdout=log_f,
            stderr=log_f,
            text=True,
            check=True,
        )
