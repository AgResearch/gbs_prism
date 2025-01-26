import logging
import os.path
import subprocess

from agr.util.path import remove_if_exists

logger = logging.getLogger(__name__)


def run_kmer_analysis(in_path: str, out_path: str, input_filetype: str, kmer_size: int):
    log_path = "%s.log" % out_path.removesuffix(".1")
    with open(log_path, "w") as log_f:
        remove_if_exists(out_path)
        # kmer_prism drops turds in the current directory and doesn't pickup after itself,
        # so we run with cwd as a subdirectory of the output file
        out_dir = os.path.dirname(out_path)
        kmer_prism_workdir = os.path.join(out_dir, "work")
        os.makedirs(kmer_prism_workdir, exist_ok=True)
        _ = subprocess.run(
            [
                "kmer_prism",
                "--input_filetype",
                input_filetype,
                "--kmer_size",
                str(kmer_size),
                "--output_filename",
                out_path,
                in_path,
            ],
            stdout=log_f,
            stderr=log_f,
            text=True,
            check=True,
            cwd=kmer_prism_workdir,
        )
