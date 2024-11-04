import sys
import tempfile
from subprocess import DEVNULL, PIPE
from agr.util import StdioRedirect


def eprint(*args, **kwargs):
    """Print to stderr"""
    print(*args, file=sys.stderr, **kwargs)


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


def test_stdio_redirect_devnull():
    """This is a bit awkward to test, suggest commenting out the DEVNULL and running `pytest -s`"""
    with StdioRedirect(stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL):
        print("gibber jabber on stdout")
        eprint("more gibber jabber on stderr")
        stdin_text = sys.stdin.read()
        assert len(stdin_text) == 0


def test_stdio_redirect_pipe():
    with StdioRedirect(stdout=PIPE) as red:
        print("the good oil flowin' down that ol' pipe")
        assert red.stdout is not None  # because PIPE
        stdout = red.stdout.read()
        assert stdout == "the good oil flowin' down that ol' pipe\n"

    with StdioRedirect(stderr=PIPE) as red:
        eprint("oops")
        assert red.stderr is not None  # because PIPE
        stderr = red.stderr.read()
        assert stderr == "oops\n"

    with StdioRedirect(stdin=PIPE, stdout=PIPE) as red:
        print("feeding the snake", file=red.stdin)
        assert red.stdin is not None  # because PIPE
        _ = red.stdin.close()
        regurgitation = sys.stdin.read()
        print(regurgitation)
        assert red.stdout is not None  # because PIPE
        excretion = red.stdout.read()
        # we accumulated a newline with each print, so:
        assert excretion == "feeding the snake\n\n"
