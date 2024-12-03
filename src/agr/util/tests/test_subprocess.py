from agr.util.subprocess import capture_regex


def test_capture_regex_stdout():
    actual = capture_regex(["echo", "abc123def"], r"^abc(\d*)")
    assert actual == "123"


def test_capture_regex_stderr():
    actual = capture_regex(
        ["bash", "-c", "echo abc123def; echo abc99k >&2"],
        r"^abc(\d*)",
        from_stderr=True,
    )
    assert actual == "99"


def test_seqtk_version_cheat():
    actual = capture_regex(
        ["echo", "Usage:   seqtk \\<command> \\<arguments>\nVersion: 1.3.5"],
        r"(?ms).*^Version:\s*(\S+)",
    )
    assert actual == "1.3.5"
