import logging
from dataclasses import dataclass
from redun import task, File

from agr.seq.sample_sheet import SampleSheet

logger = logging.getLogger(__name__)


@dataclass
class CookSampleSheetOutput:
    """Dataclass to collect the outputs of processed sample sheet."""

    sample_sheet: File
    expected_fastq: set[str]
    gbs_libraries: list[str]


@task()
def cook_sample_sheet(
    in_path: str,
    out_path: str,
    impute_lanes=[1, 2],
) -> CookSampleSheetOutput:
    """Process a raw sample sheet into a form compatiable with bclconvert et al."""
    sample_sheet = SampleSheet(in_path, impute_lanes=impute_lanes)
    sample_sheet.write(out_path)

    return CookSampleSheetOutput(
        sample_sheet=File(out_path),
        expected_fastq=sample_sheet.fastq_files,
        gbs_libraries=sample_sheet.gbs_libraries,
    )
