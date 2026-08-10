import os.path
import re
from dataclasses import dataclass
from typing import Self


class RunNameError(Exception):
    pass


def flowcell_id(run: str) -> str:
    """An MGI run name is the bare flowcell id, e.g. DL100018469.

    This must agree with gquery's `Mgi.parse_flowcell_moniker`, which returns an
    underscore-free run name unchanged: `get_keyfile_for_tassel` and
    `gbs_target_spec` look the keyfile back up by the flowcell derived here, and a
    disagreement returns an empty result rather than an error.

    Illumina run names are rejected rather than parsed. gquery does the same, and
    this pipeline no longer has an Illumina path for the answer to be useful to.
    """
    moniker = run.strip()

    if "_" in moniker or "/" in moniker:
        raise RunNameError(
            "%s does not look like an MGI run name - MGI run names are the bare "
            "flowcell id, with no underscores" % run
        )

    return moniker


# What FastQC strips from an input filename before appending `_fastqc.html`/`.zip`.
# Compression first, then the format extension, matching FastQC's own behaviour.
_FASTQC_COMPRESSION_SUFFIXES = (".gz", ".bz2")
_FASTQC_FORMAT_SUFFIXES = (".fastq", ".fq", ".txt", ".sam", ".bam")


def fastqc_basename(in_path: str) -> str:
    """Predict the stem FastQC will use for its output files.

    This has to match FastQC exactly. The task declares the html and zip as
    `expected_paths`, so a mismatch makes redun report a job that succeeded as a
    failure - and one failed QC task fails the whole run.

    The MGI switch is what exposed this: bcl-convert wrote `.fastq.gz`, so stripping
    `.gz` then `.fastq` was sufficient, but splitBarcode writes **`.fq.gz`**, which
    left `.fq` dangling and predicted `X.fq_fastqc.html` for a file FastQC actually
    named `X_fastqc.html`. Listing the extensions FastQC recognises makes it correct
    for both, and for the `.bz2`/`.txt`/`.sam`/`.bam` inputs it also accepts.
    """
    basename = os.path.basename(in_path)
    for suffix in _FASTQC_COMPRESSION_SUFFIXES:
        if basename.endswith(suffix):
            basename = basename[: -len(suffix)]
            break
    for suffix in _FASTQC_FORMAT_SUFFIXES:
        if basename.endswith(suffix):
            basename = basename[: -len(suffix)]
            break
    return basename


def fastq_name_for_tassel3(libname: str, fcid: str) -> str:
    """Tassel3 is very fussy about what filenames it accepts for FASTQ files.

    A library's lanes are merged into a single fastq before Tassel3 sees it, so the
    lane index is always 1 - matching the `_s_1_` link gquery writes into
    `gbskeyfilefact`. The source filename plays no part; it used to, via
    bcl-convert's `_L00<n>_`, which merged fastqs never carry.
    """
    return "%s_%s_s_1_fastq.txt.gz" % (libname, fcid)


@dataclass
class Cohort:
    libname: str
    qc_cohort: str
    gbs_cohort: str
    enzyme: str

    def __str__(self):
        return "%s.%s.%s.%s" % (
            self.libname,
            self.qc_cohort,
            self.gbs_cohort,
            self.enzyme,
        )

    @property
    def name(self):
        return str(self)

    @classmethod
    def parse(cls, cohort_str: str) -> Self:
        fields = cohort_str.split(".")
        assert len(fields) == 4, (
            "expected four dot-separated fields in cohort %s" % cohort_str
        )
        (libname, qc_cohort, gbs_cohort, enzyme) = tuple(fields)
        return cls(
            libname=libname, qc_cohort=qc_cohort, gbs_cohort=gbs_cohort, enzyme=enzyme
        )
