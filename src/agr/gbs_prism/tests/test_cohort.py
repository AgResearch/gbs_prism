from agr.gbs_prism.cohort import Cohort


def test_parse_cohort():
    c = Cohort("SQ0756.all.DEER.PstI", run_name="run123")
    assert c.libname == "SQ0756"
    assert c.qc_cohort == "all"
    assert c.gbs_cohort == "DEER"
    assert c.enzyme == "PstI"
