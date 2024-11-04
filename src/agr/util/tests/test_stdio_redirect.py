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
        _ = sys.stdout.close()
        stdout = red.stdout.read()
        assert stdout == "the good oil flowin' down that ol' pipe\n"

    with StdioRedirect(stdout=PIPE) as red:
        print("the good oil flowin' down that ol' pipe")
        (stdout, _) = red.communicate()
        assert stdout == "the good oil flowin' down that ol' pipe\n"

    with StdioRedirect(stderr=PIPE) as red:
        eprint("oops")
        assert red.stderr is not None  # because PIPE
        _ = sys.stderr.close()
        stderr = red.stderr.read()
        assert stderr == "oops\n"

    with StdioRedirect(stderr=PIPE) as red:
        eprint("oops")
        (_, stderr) = red.communicate()
        assert stderr == "oops\n"

    with StdioRedirect(stdout=PIPE, stderr=PIPE) as red:
        print("good boy")
        eprint("bad boy")
        (stdout, stderr) = red.communicate()
        assert stdout == "good boy\n"
        assert stderr == "bad boy\n"

    with StdioRedirect(stdin=PIPE, stdout=PIPE) as red:
        print("feeding the snake", file=red.stdin)
        assert red.stdin is not None  # because PIPE
        _ = red.stdin.close()
        regurgitation = sys.stdin.read()
        print(regurgitation)
        _ = sys.stdout.close()
        assert red.stdout is not None  # because PIPE
        excretion = red.stdout.read()
        # we accumulated a newline with each print, so:
        assert excretion == "feeding the snake\n\n"
