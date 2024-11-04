import os
import subprocess
import sys
from io import TextIOBase


class StdioRedirect:
    """
    Context manager for temporary redirect of any or all of stdin, stdout, stderr.
    API is modelled on `subprocess.Popen`.

    Each of `stdin`, `stdout`, `stderr` may be any of:
      - `None`
      - an open file object
      - `subprocess.DEVNULL`
      - `subprocess.PIPE`

    Raw file descriptors are not currently supported.

    Also, only text mode is supported.  Python is rather uncomfortable with binary stdout, and YAGNI.

    Example:

    with StdioRedirect(stdout=f):
        print("hello world in file")
    print("hello world to console, probably")
    """

    def __init__(self, stdin=None, stdout=None, stderr=None):
        self._stdin_close_on_exit = False
        self._stdin_writer = None
        if stdin is None:
            self._stdin = stdin
        elif isinstance(stdin, TextIOBase):
            self._stdin = stdin
        elif stdin == subprocess.DEVNULL:
            self._stdin = open(os.devnull, "r")
            self._stdin_close_on_exit = True
        elif stdin == subprocess.PIPE:
            (r, w) = os.pipe()
            self._stdin = os.fdopen(r, "r")
            self._stdin_writer = os.fdopen(w, "w")
            self._stdin_close_on_exit = True
        else:
            assert False, "unsupported value for stdin, %s" % repr(stdin)
        self._saved_stdin = None

        self._stdout_close_on_exit = False
        self._stdout_reader = None
        if stdout is None:
            self._stdout = stdout
        elif isinstance(stdout, TextIOBase):
            self._stdout = stdout
        elif stdout == subprocess.DEVNULL:
            self._stdout = open(os.devnull, "w")
            self._stdout_close_on_exit = True
        elif stdout == subprocess.PIPE:
            (r, w) = os.pipe()
            self._stdout = os.fdopen(w, "w")
            self._stdout_reader = os.fdopen(r, "r")
            self._stdout_close_on_exit = True
        else:
            assert False, "unsupported value for stdout, %s" % repr(stdout)
        self._saved_stdout = None

        self._stderr_close_on_exit = False
        self._stderr_reader = None
        if stderr is None:
            self._stderr = stderr
        elif isinstance(stderr, TextIOBase):
            self._stderr = stderr
        elif stderr == subprocess.DEVNULL:
            self._stderr = open(os.devnull, "w")
            self._stderr_close_on_exit = True
        elif stderr == subprocess.PIPE:
            (r, w) = os.pipe()
            self._stderr = os.fdopen(w, "w")
            self._stderr_reader = os.fdopen(r, "r")
            self._stderr_close_on_exit = True
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
        return self

    def __exit__(self, *_):
        if self._stdin is not None:
            sys.stdin = self._saved_stdin
            if self._stdin_close_on_exit:
                self._stdin.close()
        if self._stdout is not None:
            sys.stdout = self._saved_stdout
            if self._stdout_close_on_exit:
                self._stdout.close()
        if self._stderr is not None:
            sys.stderr = self._saved_stderr
            if self._stderr_close_on_exit:
                self._stderr.close()

    @property
    def stdin(self):
        """If the stdin argument was PIPE, this attribute is a writeable text stream object as returned by open(). If the stdin argument was not PIPE, this attribute is None."""
        return self._stdin_writer

    @property
    def stdout(self):
        """If the stdout argument was PIPE, this attribute is a readable text stream object as returned by open(). If the stdout argument was not PIPE, this attribute is None."""
        return self._stdout_reader

    @property
    def stderr(self):
        """If the stderr argument was PIPE, this attribute is a readable text stream object as returned by open(). If the stderr argument was not PIPE, this attribute is None."""
        return self._stderr_reader

    def communicate(self):
        """A simplified version of `communicate` which doesn't support passing in `stdin`.

        The reason for the simplification is that passing `stdin` significantly complicates the
        implementation, and YAGNI.

        See https://github.com/python/cpython/blob/9441993f272f42e4a97d90616ec629a11c06aa3a/Lib/subprocess.py#L2068
        """

        if self._stdout_reader is not None:
            if self._stdout_close_on_exit and self._stdout is not None:
                self._stdout.close()
                self._stdout_close_on_exit = False
            stdout = self._stdout_reader.read()
        else:
            stdout = None

        if self._stderr_reader is not None:
            if self._stderr_close_on_exit and self._stderr is not None:
                self._stderr.close()
                self._stderr_close_on_exit = False
            stderr = self._stderr_reader.read()
        else:
            stderr = None

        return (stdout, stderr)
