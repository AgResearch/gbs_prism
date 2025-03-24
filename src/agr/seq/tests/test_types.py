from agr.seq.types import flowcell_id, Cohort


def test_flowcell_id():
    assert flowcell_id("240621_A01439_0276_AH33J5DRX5") == "H33J5DRX5"


def test_parse_cohort():
    c = Cohort.parse("SQ0756.all.DEER.PstI")
    assert c.libname == "SQ0756"
    assert c.qc_cohort == "all"
    assert c.gbs_cohort == "DEER"
    assert c.enzyme == "PstI"
