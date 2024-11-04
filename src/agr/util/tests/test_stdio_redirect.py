import sys
import tempfile
from subprocess import DEVNULL, PIPE
from agr.util import StdioRedirect


def eprint(*args, **kwargs):
    """Print to stderr"""
    print(*args, file=sys.stderr, **kwargs)


def test_stdio_redirect_file_stdout():
    testfile = tempfile.TemporaryFile(mode="w+")
    with StdioRedirect(stdout=testfile, text=True):
        print("gibber jabber")
    _ = testfile.seek(0)
    actual = testfile.read()
    assert actual == "gibber jabber\n"


def test_stdio_redirect_file_stderr():
    testfile = tempfile.TemporaryFile(mode="w+")
    with StdioRedirect(stderr=testfile, text=True):
        eprint("gibber jabber")
    _ = testfile.seek(0)
    actual = testfile.read()
    assert actual == "gibber jabber\n"


def test_stdio_redirect_devnull():
    """This is a bit awkward to test, suggest commenting out the DEVNULL and running `pytest -s`"""
    with StdioRedirect(stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL, text=True):
        print("gibber jabber on stdout")
        eprint("more gibber jabber on stderr")
        stdin_text = sys.stdin.read()
        assert len(stdin_text) == 0


def test_stdio_redirect_pipe():
    with StdioRedirect(stdout=PIPE, text=True) as red:
        print("the good oil flowin' down that ol' pipe")
        (stdout, _) = red.communicate()
        assert stdout == "the good oil flowin' down that ol' pipe\n"

    with StdioRedirect(stderr=PIPE, text=True) as red:
        eprint("oops")
        (_, stderr) = red.communicate()
        assert stderr == "oops\n"

    with StdioRedirect(stdout=PIPE, stderr=PIPE, text=True) as red:
        print("good boy")
        eprint("bad boy")
        (stdout, stderr) = red.communicate()
        assert stdout == "good boy\n"
        assert stderr == "bad boy\n"
