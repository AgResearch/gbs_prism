from dataclasses import dataclass


def flowcell_id(run: str) -> str:
    return run.split("_")[3][1:]


@dataclass(frozen=True)
class Stage2TargetConfig:
    """Paths and monikers for stage 2 targets."""

    gbs_paths: str
    fastq_link_farm: str
    bwa_sample_moniker: str
