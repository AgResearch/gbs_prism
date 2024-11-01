import logging
import os.path

from agr.util import StdioRedirect
from .kmer_prism import KmerPrism

logger = logging.getLogger(__name__)


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

    def output(self, fastq_file: str) -> str:
        return "%s.1" % self._monikered_out_basepath(fastq_file)

    def run(self, fastq_path: str):
        out_path = self.output(fastq_path)
        with open(self.log_path(fastq_path), "w") as log_f:
            with StdioRedirect(stdout=log_f, stderr=log_f):
                self._kmer_prism.run([fastq_path], output_filename=out_path)
