import logging
import os.path

from dataclasses import dataclass
from redun import task, File

from agr.seq.sample_sheet import SampleSheet

logger = logging.getLogger(__name__)


@dataclass
class CookSampleSheetOutput:
    """Dataclass to collect the outputs of processed sample sheet."""

    sample_sheet: File
    expected_fastq: set[str]


@task()
def cook_sample_sheet(
    in_file: File,
    out_path: str,
    impute_lanes: list[int] = [1, 2],
) -> CookSampleSheetOutput:
    """Process a raw sample sheet into a form compatible with bclconvert et al.

    The GenerateKeyfile section is excluded from the written output so that
    changes to it don't invalidate downstream tasks (BCL-convert, FastQC, etc.)
    that don't depend on it.

    The file is only rewritten when its content actually changes, so that
    redun's mtime-based File hashing correctly skips downstream tasks when
    only the GenerateKeyfile section was modified.
    """

    # create base SampleSheet/ directory beside SampleSheet.csv
    os.makedirs(os.path.join(os.path.dirname(out_path), "SampleSheet"), exist_ok=True)

    sample_sheet = SampleSheet(in_file.path, impute_lanes=impute_lanes)
    new_content = sample_sheet.render(exclude_sections=["GenerateKeyfile"])

    # only rewrite if content changed, preserving mtime for redun File caching
    existing_content = None
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing_content = f.read()

    if existing_content != new_content:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            f.write(new_content)

    return CookSampleSheetOutput(
        sample_sheet=File(out_path),
        expected_fastq=sample_sheet.fastq_files,
    )


@task()
def get_gbs_libraries(in_file: File) -> list[str]:
    """Extract GBS library names from the GenerateKeyfile section of a raw sample sheet."""
    sample_sheet = SampleSheet(in_file.path)
    return sample_sheet.gbs_libraries
