import sys
from io import TextIOBase


class StdioRedirect:
    """
    Context manager for temporary redirect of any or all of stdin, stdout, stderr.
    API is modelled on `subprocess.Popen`.

    Each of `stdin`, `stdout`, `stderr` may be any of:
      - `None`
      - an open file object

    Raw file descriptors are not currently supported.

    Also, only text mode is supported.  Python is rather uncomfortable with binary stdout, and YAGNI.

    Example:

    with StdioRedirect(stdout=f):
        print("hello world in file")
    print("hello world to console, probably")

    Note: an earlier version of this class supported PIPE, but this was removed as too complex.  (See e.g. subprocess communicate implementation).
    """

    def __init__(self, stdin=None, stdout=None, stderr=None):
        if stdin is None:
            self._stdin = stdin
        elif isinstance(stdin, TextIOBase):
            self._stdin = stdin
        else:
            assert False, "unsupported value for stdin, %s" % repr(stdin)
        self._saved_stdin = None

        if stdout is None:
            self._stdout = stdout
        elif isinstance(stdout, TextIOBase):
            self._stdout = stdout
        else:
            assert False, "unsupported value for stdout, %s" % repr(stdout)
        self._saved_stdout = None

        if stderr is None:
            self._stderr = stderr
        elif isinstance(stderr, TextIOBase):
            self._stderr = stderr
        else:
            assert False, "unsupported value for stderr, %s" % repr(stderr)
        self._saved_stderr = None

    def __enter__(self):
        if self._stdin is not None:
            self._saved_stdin = sys.stdin
            sys.stdin = self._stdin
        if self._stdout is not None:
            self._saved_stdout = sys.stdout
            sys.stdout = self._stdout
        if self._stderr is not None:
            self._saved_stderr = sys.stderr
            sys.stderr = self._stderr

    def __exit__(self, *_):
        if self._stdin is not None:
            sys.stdin = self._saved_stdin
        if self._stdout is not None:
            sys.stdout = self._saved_stdout
        if self._stderr is not None:
            sys.stderr = self._saved_stderr
