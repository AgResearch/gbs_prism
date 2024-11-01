import os.path

from agr.seq.sample_sheet import SampleSheet


def test_sample_sheet():
    ss = SampleSheet(os.path.join(os.path.dirname(__file__), "TestSampleSheet.csv"))
    generate_keyfile_section = ss.get_section("GenerateKeyFile")
    assert generate_keyfile_section is not None

    sample_ids = generate_keyfile_section.named_column("Sample_ID")
    assert sample_ids is not None
    assert sample_ids == ["SQ2426", "SQ2426", "SQ2427", "SQ2428"]

    plateids = generate_keyfile_section.named_column("plateid")
    assert plateids is not None
    assert plateids == ["12121", "5024", "5033", "5081"]
