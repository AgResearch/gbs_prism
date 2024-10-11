# a dataclass for ease of access to the main config
from dataclasses import dataclass


@dataclass
class Config:
    seq_root: str
    postprocessing_root: str
    run: str
    gbs_backup_dir: str
    key_files_dir: str
    fastq_link_farm: str
