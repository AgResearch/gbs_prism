from agr.gbs_prism.types import flowcell_id


def test_flowcell_id():
    assert flowcell_id("240621_A01439_0276_AH33J5DRX5") == "H33J5DRX5"
