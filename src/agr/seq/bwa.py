import logging
import subprocess

from agr.util import eprint

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
                "10",
                reference,
                in_path,
            ]
            eprint(" ".join(bwa_command))
            _ = subprocess.run(
                bwa_command,
                stdout=out_f,
                check=True,
            )
