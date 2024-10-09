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
        self.stdin = stdin
        self.saved_stdin = None
        self.stdout = stdout
        self.saved_stdout = None
        self.stderr = stderr
        self.saved_stderr = None

    def __enter__(self):
        if self.stdin is not None:
            self.saved_stdin = sys.stdin
            sys.stdin = self.stdin
        if self.stdout is not None:
            self.saved_stdout = sys.stdout
            sys.stdout = self.stdout
        if self.stderr is not None:
            self.saved_stderr = sys.stderr
            sys.stderr = self.stderr

    def __exit__(self, *_):
        if self.stdin is not None:
            sys.stdin = self.saved_stdin
        if self.stdout is not None:
            sys.stdout = self.saved_stdout
        if self.stderr is not None:
            sys.stderr = self.saved_stderr
