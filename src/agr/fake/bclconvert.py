import gzip
import logging
import os.path
import pathlib
import shutil

from agr.seq.sample_sheet import SampleSheet
from agr.seq.bclconvert import BclConvert as RealBclConvert, BclConvertError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BclConvert(RealBclConvert):
    def __init__(
        self, in_dir: str, sample_sheet_path: str, out_dir: str, n_reads=200000
    ):
        super(BclConvert, self).__init__(
            in_dir=in_dir, sample_sheet_path=sample_sheet_path, out_dir=out_dir
        )

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
            candidate_run_dir = (
                "/dataset/%s/scratch/postprocessing/illumina/novaseq/%s"
                % (dataset, run_name)
            )
            if os.path.isdir(candidate_run_dir):
                break
        if not os.path.isdir(candidate_run_dir):
            raise BclConvertError(
                "failed to find run %s in any of %s"
                % (run_name, " ".join(illumina_datasets))
            )
        self._real_fastq_dir = os.path.join(
            candidate_run_dir, "SampleSheet", "bclconvert"
        )
        self._real_top_unknown_path = os.path.join(
            self._real_fastq_dir, "Reports", "Top_Unknown_Barcodes.csv"
        )
        self._n_reads = n_reads

    def run(self):
        logger.warning(
            "fake BclConvert with %d reads from %s"
            % (self._n_reads, self._real_fastq_dir)
        )
        sample_sheet = SampleSheet(self._sample_sheet_path, impute_lanes=[1, 2])

        for fastq_file in sample_sheet.fastq_files:
            with gzip.open(
                os.path.join(self._real_fastq_dir, fastq_file), mode="r"
            ) as real_gz:
                with gzip.open(
                    os.path.join(self._out_dir, fastq_file), mode="w"
                ) as fake_gz:
                    for _ in range(self._n_reads * 4):  # 4 lines per read
                        line = next(real_gz)
                        _ = fake_gz.write(line)

        _ = shutil.copyfile(self._real_top_unknown_path, self.top_unknown_path)

        # TODO: probably eventually remove this, seems no good reason to keep the fastq complete marker file:
        pathlib.Path(self.fastq_complete_path).touch()
