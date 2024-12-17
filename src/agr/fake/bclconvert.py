import gzip
import logging
import os.path
import shutil
from typing import Optional

from agr.seq.sample_sheet import SampleSheet

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BclConvertError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        if self._e is None:
            return self._msg
        else:
            return "%s: %s" % (self._msg, str(self._e))


def bclconvert(in_dir: str, sample_sheet_path: str, out_dir: str, n_reads=2000000):
    # find the real run
    run_name = os.path.basename(in_dir)
    illumina_datasets = [
        "2024_illumina_sequencing_d",
        "2024_illumina_sequencing_e",
        "2023_illumina_sequencing_c",
        "2023_illumina_sequencing_b",
        "2023_illumina_sequencing_a",
    ]
    candidate_run_dir = "/not-found"
    for dataset in illumina_datasets:
        candidate_run_dir = "/dataset/%s/scratch/postprocessing/illumina/novaseq/%s" % (
            dataset,
            run_name,
        )
        if os.path.isdir(candidate_run_dir):
            break
    if not os.path.isdir(candidate_run_dir):
        raise BclConvertError(
            "failed to find run %s in any of %s"
            % (run_name, " ".join(illumina_datasets))
        )
    real_fastq_dir = os.path.join(candidate_run_dir, "SampleSheet", "bclconvert")
    real_top_unknown_path = os.path.join(
        real_fastq_dir, "Reports", "Top_Unknown_Barcodes.csv"
    )
    real_logs_dir = os.path.join(real_fastq_dir, "Logs")

    logger.warning("fake BclConvert with %d reads from %s" % (n_reads, real_fastq_dir))
    sample_sheet = SampleSheet(sample_sheet_path, impute_lanes=[1, 2])

    for fastq_file in sample_sheet.fastq_files:
        with gzip.open(os.path.join(real_fastq_dir, fastq_file), mode="r") as real_gz:
            with gzip.open(os.path.join(out_dir, fastq_file), mode="w") as fake_gz:
                for _ in range(n_reads * 4):  # 4 lines per read
                    line = next(real_gz)
                    _ = fake_gz.write(line)

    reports_dir = os.path.join(out_dir, "Reports")
    os.makedirs(reports_dir, exist_ok=True)
    top_unknown_path = os.path.join(reports_dir, "Top_Unknown_Barcodes.csv")
    _ = shutil.copyfile(real_top_unknown_path, top_unknown_path)

    logs_dir = os.path.join(out_dir, "Logs")
    _ = shutil.copytree(real_logs_dir, logs_dir)

    # this is completely bogus, a naive attempt to meet the contract of the nf-core bclconvert module
    interop_dir = os.path.join(out_dir, "InterOp")
    os.makedirs(interop_dir, exist_ok=True)
    with open(os.path.join(interop_dir, "dummy.bin"), "w") as dummy_interop_f:
        _ = dummy_interop_f.write("The bogus file makes fake bclconvert look more real")
