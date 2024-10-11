import sys


class StdioRedirect:
    """
    Context manager for temporary redirect of any or all of stdin, stdout, stderr.

    Example:

    with StdioRedirect(stdout=f):
        print("hello world in file")
    print("hello world to console, probably")
    """

    def __init__(self, stdin=None, stdout=None, stderr=None):
        self._stdin = stdin
        self._saved_stdin = None
        self._stdout = stdout
        self._saved_stdout = None
        self._stderr = stderr
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
