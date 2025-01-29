import io
import shutil
import subprocess
import tempfile

# see comment below about own exception class
# TODO: find out what's broken with redun not understanding own exceptions, and reinstate this
#
# class CalledProcessError(Exception):
#     def __init__(self, returncode: int, cmd: List[str], stderr: str | bytes):
#         self.returncode = returncode
#         self.cmd = cmd
#         self.stderr = stderr

#     def __str__(self) -> str:
#         return f"Command `{' '.join(self.cmd)}` failed with exit status {self.returncode}\n{self.stderr}"


def run_catching_stderr(*args, **kwargs):
    """Just like subprocess.run, but in case of check=True will catch stderr and format into the exception."""
    is_text = (
        hasattr(kwargs, "encoding")
        or hasattr(kwargs, "errors")
        or kwargs.get("text", False)
    )

    # use original stderr only if it is a file object matching `is_text`
    original_stderr = kwargs.get("stderr")
    if original_stderr is not None and not (
        (is_text and isinstance(original_stderr, io.TextIOBase))
        or (
            (not is_text)
            and (
                isinstance(original_stderr, io.BufferedIOBase)
                or isinstance(original_stderr, io.RawIOBase)
            )
        )
    ):
        original_stderr = None

    with tempfile.TemporaryFile(mode="w+" if is_text else "wb+") as tmp_f:
        try:
            return subprocess.run(*args, **(kwargs | {"stderr": tmp_f}))

        except subprocess.CalledProcessError as e:
            _ = tmp_f.seek(0)
            # if we attempt to use our own exception class here, redun doesn't understand it,
            # and we simply see Unknown in the console
            raise Exception(f"`{' '.join(e.cmd)}` failed:\n{tmp_f.read()}") from e

        finally:
            if original_stderr is not None:
                _ = tmp_f.seek(0)
                shutil.copyfileobj(tmp_f, original_stderr)
