import tempfile
from agr.util import StdioRedirect, eprint


def test_stdio_redirect_file_stdout():
    testfile = tempfile.TemporaryFile(mode="w+")
    with StdioRedirect(stdout=testfile):
        print("gibber jabber")
    _ = testfile.seek(0)
    actual = testfile.read()
    assert actual == "gibber jabber\n"


def test_stdio_redirect_file_stderr():
    testfile = tempfile.TemporaryFile(mode="w+")
    with StdioRedirect(stderr=testfile):
        eprint("gibber jabber")
    _ = testfile.seek(0)
    actual = testfile.read()
    assert actual == "gibber jabber\n"
