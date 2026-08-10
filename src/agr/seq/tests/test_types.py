import pytest

from agr.seq.types import (
    Cohort,
    RunNameError,
    fastq_name_for_tassel3,
    flowcell_id,
)


def test_flowcell_id_is_the_mgi_run_name():
    """An MGI run name *is* its flowcell id.

    This must agree with gquery's Mgi.parse_flowcell_moniker, which returns the run
    name unchanged. If the two derivations diverge, get_keyfile_for_tassel looks the
    keyfile back up under the wrong flowcell and gets an empty result with no error.
    """
    assert flowcell_id("DL100018469") == "DL100018469"


def test_flowcell_id_strips_surrounding_whitespace():
    assert flowcell_id("  DL100018469\n") == "DL100018469"


def test_flowcell_id_rejects_an_illumina_run_name():
    """Underscores mean an Illumina run name, which this pipeline no longer handles.

    gquery's Mgi.parse_flowcell_moniker raises on the same input rather than
    silently mangling it; failing here too keeps a mistaken run name loud.
    """
    with pytest.raises(RunNameError):
        _ = flowcell_id("240621_A01439_0276_AH33J5DRX5")


def test_fastq_name_for_tassel3_names_a_merged_fastq():
    """Tassel3 accepts only <libname>_<fcid>_s_<lane>_fastq.txt.gz.

    MGI fastqs are merged across lanes before Tassel3 sees them, so there is exactly
    one per library and the lane is always 1 - matching the _s_1_ link gquery writes
    into gbskeyfilefact.

    The name is derived wholly from the library and flowcell. The source filename is
    not a parameter, which is what retires the old silent failure: the previous
    implementation searched it for bcl-convert's _L00<n>_ and, on no match, returned
    it *unchanged*. Merged fastqs never match, so every MGI file reached Tassel3
    under a name it rejects, with no error.
    """
    assert (
        fastq_name_for_tassel3("SQ5420", "DL100018469")
        == "SQ5420_DL100018469_s_1_fastq.txt.gz"
    )


def test_parse_cohort():
    c = Cohort.parse("SQ0756.all.DEER.PstI")
    assert c.libname == "SQ0756"
    assert c.qc_cohort == "all"
    assert c.gbs_cohort == "DEER"
    assert c.enzyme == "PstI"
