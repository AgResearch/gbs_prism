import logging

from agr.util import StdioRedirect
from .kmer_prism import KmerPrism

logger = logging.getLogger(__name__)


def run_kmer_analysis(in_path: str, out_path: str, kmer_prism: KmerPrism):
    err_path = "%s.log" % out_path.removesuffix(".1")
    with open(err_path, "w") as err_f:
        with StdioRedirect(stdout=err_f, stderr=err_f):
            kmer_prism.run([in_path], output_filename=out_path)
