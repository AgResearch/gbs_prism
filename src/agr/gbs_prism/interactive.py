import json
import logging
import os.path
from functools import cached_property

from agr.seq.sequencer_run import SequencerRun
from agr.seq.mgi.sample_sheet import MgiSampleSheet, read_sample_sheet

from agr.gbs_prism.paths import Paths
from agr.util.path import expand

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M",
)
# for noisy_module in ["asyncio", "pulp.apis.core", "urllib3"]:
#     logging.getLogger(noisy_module).setLevel(logging.WARN)


class RunContext:
    """
    Class for interactive use of the pipeline, from the Python REPL.
    Provides convenience objects as lazy properties.

    Extend as required, this is not yet complete.
    """

    def __init__(self, run_name: str, context_file: str):
        with open(expand(context_file), "r") as context_f:
            self._context = json.load(context_f)
            self._path_context = self._context["path"]
            self._run_name = run_name
            self._paths = Paths(self.postprocessing_root, self._run_name)

    @property
    def paths(self) -> Paths:
        return self._paths

    @cached_property
    def seq_root(self) -> str:
        return expand(self._path_context["seq_root"])

    @cached_property
    def postprocessing_root(self) -> str:
        return expand(self._path_context["postprocessing_root"])

    @cached_property
    def gbs_backup_dir(self) -> str:
        return expand(self._path_context["gbs_backup_dir"])

    @cached_property
    def keyfiles_dir(self) -> str:
        return expand(self._path_context["keyfiles_dir"])

    @cached_property
    def fastq_link_farm(self) -> str:
        return expand(self._path_context["fastq_link_farm"])

    @cached_property
    def sample_sheet_root(self) -> str:
        return expand(self._path_context["sample_sheet_root"])

    @cached_property
    def sequencer_run(self) -> SequencerRun:
        return SequencerRun(self.seq_root, self._run_name)

    @cached_property
    def sample_sheet_path(self) -> str:
        """MGI sheets live outside the run tree, named for the flowcell."""
        return os.path.join(self.sample_sheet_root, "%s.csv" % self._run_name)

    @cached_property
    def sample_sheet(self) -> MgiSampleSheet:
        return read_sample_sheet(self.sample_sheet_path)
