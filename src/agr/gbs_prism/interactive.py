import json
import logging
import os.path
from functools import cached_property
from typing import Literal

from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet
from agr.seq.bclconvert import BclConvert
from agr.fake.bclconvert import FakeBclConvert, create_real_or_fake_bcl_convert

from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import Paths
from agr.seq.dedupe import dedupe
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

    def __init__(
        self,
        run_name: str,
        context_file: str,
        platform: Literal["iseq", "miseq", "novaseq"] = "novaseq",
        impute_lanes=[1, 2],
    ):
        with open(expand(context_file), "r") as context_f:
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
    def sequencer_run(self) -> SequencerRun:
        return SequencerRun(self.seq_root, self._run_name)

    @cached_property
    def sample_sheet(self) -> SampleSheet:
        return SampleSheet(
            self.sequencer_run.sample_sheet_path, impute_lanes=self._impute_lanes
        )

    @cached_property
    def bclconvert(self) -> BclConvert | FakeBclConvert:
        return create_real_or_fake_bcl_convert(
            self.sequencer_run.dir,
            sample_sheet_path=self.paths.seq.sample_sheet_path,
            out_dir=self.paths.seq.bclconvert_dir,
            bcl_convert_context=self._context.get("bcl_convert"),
        )

    @cached_property
    def gbs_keyfiles(self) -> GbsKeyfiles:
        return GbsKeyfiles(
            sequencer_run=self.sequencer_run,
            sample_sheet_path=self.paths.seq.sample_sheet_path,
            root=self.paths.illumina_platform_root,
            out_dir=self.keyfiles_dir,
            fastq_link_farm=self.fastq_link_farm,
            backup_dir=self.gbs_backup_dir,
        )

    def dedupe(self, fastq_path: str):
        """Dedupe a single fastq file (full path), info the configured output directory."""
        out_dir = self.paths.seq.dedupe_dir
        out_path = os.path.join(out_dir, os.path.basename(fastq_path))
        dedupe(
            in_path=fastq_path,
            out_path=out_path,
            tmp_dir="/tmp",  # TODO maybe need tmp_dir on large scratch partition
        )
