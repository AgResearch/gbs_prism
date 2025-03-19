import logging

import agr.util.cluster as cluster

logger = logging.getLogger(__name__)

BWA_ALN_TOOL_NAME = "bwa_aln"
BWA_SAMSE_TOOL_NAME = "bwa_samse"


class Bwa:
    def __init__(self, barcode_len: int):
        self._barcode_len = barcode_len

    @property
    def moniker(self) -> str:
        return "B%d" % self._barcode_len

    def aln_job_spec(
        self, in_path: str, out_path: str, reference: str
    ) -> cluster.Job1Spec:
        return cluster.Job1Spec(
            tool=BWA_ALN_TOOL_NAME,
            args=[
                "bwa",
                "aln",
                "-B",
                str(self._barcode_len),
                reference,
                in_path,
            ],
            stdout_path=out_path,
            stderr_path=f"{out_path}.err",
            expected_path=out_path,
        )

    def samse_job_spec(
        self, sai_path: str, fastq_path: str, out_path: str, reference: str
    ) -> cluster.Job1Spec:
        return cluster.Job1Spec(
            tool=BWA_SAMSE_TOOL_NAME,
            args=[
                "bwa",
                "samse",
                reference,
                sai_path,
                fastq_path,
            ],
            stdout_path=out_path,
            stderr_path=f"{out_path}.err",
            expected_path=out_path,
        )
