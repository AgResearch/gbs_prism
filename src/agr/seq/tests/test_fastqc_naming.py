"""Tests for predicting FastQC's output filenames.

Stdlib-only, so these run in CI.

FastQC names its output by stripping known extensions from the input, and the task
must predict that name exactly: redun checks for the file at the predicted path, so a
mismatch reports a successful job as a failure and takes the whole run down with it.
"""

import pytest

from agr.seq.types import fastqc_basename


def test_mgi_fq_gz():
    """splitBarcode writes `.fq.gz`, not Illumina's `.fastq.gz`.

    The original stripped `.gz` then `.fastq`, which leaves `.fq` dangling and
    predicts `X.fq_fastqc.html` where FastQC actually writes `X_fastqc.html`. Every
    MGI fastqc job therefore reported a spurious failure.
    """
    assert fastqc_basename("/x/DL100018469_L04_SQ5575.fq.gz") == "DL100018469_L04_SQ5575"


def test_illumina_fastq_gz():
    assert fastqc_basename("/x/SQ5051_S1_L001_R1_001.fastq.gz") == "SQ5051_S1_L001_R1_001"


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("sample.fq", "sample"),
        ("sample.fastq", "sample"),
        ("sample.fq.gz", "sample"),
        ("sample.fastq.gz", "sample"),
        ("sample.fastq.bz2", "sample"),
        ("sample.txt.gz", "sample"),
        ("sample.bam", "sample"),
        ("sample.sam", "sample"),
        # No recognised extension: FastQC leaves the name alone, so we must too.
        ("sample", "sample"),
    ],
)
def test_extensions_fastqc_recognises(filename, expected):
    assert fastqc_basename("/some/dir/" + filename) == expected


def test_only_the_trailing_extensions_are_stripped():
    """`.fq` inside the stem must survive."""
    assert fastqc_basename("/x/SQ5420.fq.reads.fq.gz") == "SQ5420.fq.reads"
