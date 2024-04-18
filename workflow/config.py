# a dataclass for ease of access to the main config
import os.path
from dataclasses import dataclass

@dataclass
class Config:
    seq_root: str
    postprocessing_root: str
    run: str 
