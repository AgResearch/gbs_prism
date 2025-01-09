import logging

from agr.util import StdioRedirect
from agr.util.path import remove_if_exists
from .kmer_prism import KmerPrism

logger = logging.getLogger(__name__)


def run_kmer_analysis(in_path: str, out_path: str, kmer_prism: KmerPrism):
    log_path = "%s.log" % out_path.removesuffix(".1")
    with open(log_path, "w") as log_f:
        with StdioRedirect(stdout=log_f, stderr=log_f):
            remove_if_exists(out_path)
            kmer_prism.run([in_path], output_filename=out_path)
