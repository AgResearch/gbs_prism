import gzip
import logging
import os.path
import pathlib
import subprocess

from agr.seq.sample_sheet import SampleSheet
from agr.seq.bclconvert import BclConvert as RealBclConvert

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BclConvert(RealBclConvert):
    def __init__(self, in_dir: str, sample_sheet_path: str, out_dir: str):
        super(BclConvert, self).__init__(
            in_dir=in_dir, sample_sheet_path=sample_sheet_path, out_dir=out_dir
        )

    def run(self):
        logger.warning("using fake BclConvert instead of real one")
        sample_sheet = SampleSheet(self._sample_sheet_path, impute_lanes=[1, 2])

        for fastq_file in sample_sheet.fastq_files:
            fastq = subprocess.run(
                [
                    "fastq_generator",
                    "generate_random_fastq_PE",
                    "200",
                    "20",
                ],
                check=True,
                capture_output=True,
            )
            with gzip.open(os.path.join(self._out_dir, fastq_file), mode="wb") as gz:
                _ = gz.write(fastq.stdout)

        # completely bogus, hopefully no-one's counting on this:
        with open(self.top_unknown_path, mode="w") as f:
            _ = f.write(
                """Lane,index,index2,# Reads,% of Unknown Barcodes,% of All Reads
1,GGGGGGGGGG,AGATCTCG,192055175,0.885274,0.182866
1,GACGAGATTA,GGGGGGGG,2300580,0.010604,0.002191
"""
            )

        # TODO: probably eventually remove this, seems no good reason to keep the fastq complete marker file:
        pathlib.Path(self.fastq_complete_path).touch()
