import logging
import os.path
from typing import Optional

from agr.prism.kmer_prism import KmerPrism
from agr.util import StdioRedirect

logger = logging.getLogger(__name__)


class KmerAnalysisError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        if self._e is None:
            return self._msg
        else:
            return "%s: %s" % (self._msg, str(self._e))


class KmerAnalysis(object):
    def __init__(self, out_dir: str, kmer_prism: KmerPrism):
        self._out_dir = out_dir
        self._kmer_prism = kmer_prism

    def _monikered_out_basepath(self, fastq_file: str) -> str:
        return os.path.join(
            self._out_dir,
            "%s.%s" % (os.path.basename(fastq_file), self._kmer_prism.moniker),
        )

    def log_path(self, fastq_file: str) -> str:
        return "%s.log" % self._monikered_out_basepath(fastq_file)

    def ensure_dirs_exist(self):
        try:
            os.makedirs(self._out_dir, exist_ok=True)
        except Exception as e:
            raise KmerAnalysisError("failed to create %s" % self._out_dir, e)
        logger.info("created %s directory" % self._out_dir)

    def output(self, fastq_file: str) -> str:
        return "%s.1" % self._monikered_out_basepath(fastq_file)

    def run(self, fastq_path: str):
        out_path = self.output(fastq_path)
        with open(self.log_path(fastq_path), "w") as log_f:
            with StdioRedirect(stdout=log_f, stderr=log_f):
                self._kmer_prism.run([fastq_path], output_filename=out_path)
