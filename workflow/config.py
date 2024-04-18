# a dataclass for ease of access to the main config
from dataclasses import dataclass

@dataclass
class Config:
    seq_root: str
    postprocessing_root: str
    run: str 
