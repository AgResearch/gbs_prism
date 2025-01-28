import logging

from agr.util.subprocess import run_catching_stderr

logger = logging.getLogger(__name__)


class Bwa:
    def __init__(self, barcode_len: int):
        self._barcode_len = barcode_len

    @property
    def moniker(self) -> str:
        return "B%d" % self._barcode_len

    def aln(self, in_path: str, out_path: str, reference: str):
        with open(out_path, "w") as out_f:
            bwa_command = [
                "bwa",
                "aln",
                "-B",
                str(self._barcode_len),
                reference,
                in_path,
            ]
            logger.info(" ".join(bwa_command))
            _ = run_catching_stderr(
                bwa_command,
                stdout=out_f,
                check=True,
            )

    def samse(self, sai_path: str, fastq_path: str, out_path: str, reference: str):
        with open(out_path, "w") as out_f:
            bwa_command = [
                "bwa",
                "samse",
                reference,
                sai_path,
                fastq_path,
            ]
            logger.info(" ".join(bwa_command))
            _ = run_catching_stderr(
                bwa_command,
                stdout=out_f,
                check=True,
            )
