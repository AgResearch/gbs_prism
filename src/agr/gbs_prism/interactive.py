import json
import os.path
from functools import cached_property
from typing import Literal

from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet
from agr.seq.bclconvert import BclConvert
from agr.fake.bclconvert import FakeBclConvert

from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import Paths
from agr.gbs_prism.redun.stage1 import create_bcl_convert


class RunContext:
    """
    Class for interactive use of the pipeline, from the Python REPL.
    Provides convenience objects as lazy properties.

    Extend as required, this is not yet complete.
    """

    def __init__(
        self,
        context_file: str,
        run_name: str,
        platform: Literal["iseq", "miseq", "novaseq"] = "novaseq",
        impute_lanes=[1, 2],
    ):
        with open(context_file, "r") as context_f:
            self._context = json.load(context_f)
            self._path_context = self._context["path"]
            self._run_name = run_name
            self._paths = Paths(self.postprocessing_root, self._run_name, platform)
            self._impute_lanes = impute_lanes

    @property
    def paths(self) -> Paths:
        return self._paths

    @cached_property
    def seq_root(self) -> str:
        return os.path.expanduser(self._path_context["seq_root"])

    @cached_property
    def postprocessing_root(self) -> str:
        return os.path.expanduser(self._path_context["postprocessing_root"])

    @cached_property
    def gbs_backup_dir(self) -> str:
        return os.path.expanduser(self._path_context["gbs_backup_dir"])

    @cached_property
    def keyfiles_dir(self) -> str:
        return os.path.expanduser(self._path_context["keyfiles_dir"])

    @cached_property
    def fastq_link_farm(self) -> str:
        return os.path.expanduser(self._path_context["fastq_link_farm"])

    @cached_property
    def sequencer_run(self) -> SequencerRun:
        return SequencerRun(self.seq_root, self._run_name)

    @cached_property
    def sample_sheet(self) -> SampleSheet:
        return SampleSheet(
            self.sequencer_run.sample_sheet_path, impute_lanes=self._impute_lanes
        )

    @cached_property
    def bclconvert(self) -> BclConvert | FakeBclConvert:
        return create_bcl_convert(
            self.sequencer_run.dir,
            sample_sheet_path=self.sample_sheet.path,
            out_dir=self.paths.seq.bclconvert_dir,
            bcl_convert_context=self._context.get("bcl_convert"),
        )

    @cached_property
    def gbs_keyfiles(self) -> GbsKeyfiles:
        return GbsKeyfiles(
            sequencer_run=self.sequencer_run,
            sample_sheet_path=self.sample_sheet.path,
            root=self.paths.illumina_platform_root,
            out_dir=self.keyfiles_dir,
            fastq_link_farm=self.fastq_link_farm,
            backup_dir=self.gbs_backup_dir,
        )
