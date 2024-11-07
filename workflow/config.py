import os.path
from dataclasses import dataclass, fields


@dataclass
class Config:
    """A dataclass for ease of access to the main config."""

    seq_root: str
    postprocessing_root: str
    run: str
    gbs_backup_dir: str
    keyfiles_dir: str
    fastq_link_farm: str

    def __post_init__(self):
        """Allow ~ to be used for specifying paths, useful in development rather than production."""
        for field in fields(self):
            raw = getattr(self, field.name)
            expanded = os.path.expanduser(raw)
            setattr(self, field.name, expanded)
