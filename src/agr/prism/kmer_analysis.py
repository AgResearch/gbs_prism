import logging
import os.path
from typing import Optional

import agr.prism.kmer_prism as kmer_prism
from agr.util.stdio_redirect import StdioRedirect

logger = logging.getLogger(__name__)


class KmerAnalysisError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self.msg = msg
        self.e = e

    def __str__(self) -> str:
        if self.e is None:
            return self.msg
        else:
            return "%s: %s" % (self.msg, str(self.e))


class KmerAnalysis(object):
    def __init__(self, out_dir: str, kmer_prism_args: kmer_prism.Args):
        self.out_dir = out_dir
        self.kmer_prism_args = kmer_prism_args

    def _monikered_out_basepath(self, fastq_file: str) -> str:
        return os.path.join(
            self.out_dir,
            "%s.%s" % (os.path.basename(fastq_file), self.kmer_prism_args.moniker),
        )

    def log_path(self, fastq_file: str) -> str:
        return "%s.log" % self._monikered_out_basepath(fastq_file)

    def ensure_dirs_exist(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except Exception as e:
            raise KmerAnalysisError("failed to create %s" % self.out_dir, e)
        logger.info("created %s directory" % self.out_dir)

    def output(self, fastq_file: str) -> str:
        return "%s.1" % self._monikered_out_basepath(fastq_file)

    def run(self, kmer_prism_args: kmer_prism.Args, fastq_path: str):
        out_path = self.output(fastq_path)
        with open(self.log_path(fastq_path), "w") as log_f:
            with StdioRedirect(stdout=log_f, stderr=log_f):
                kmer_prism.run(
                    kmer_prism_args.file_names([fastq_path]).output_filename(out_path)
                )
