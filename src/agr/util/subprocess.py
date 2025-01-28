import io
import shutil
import subprocess
import tempfile


class CalledProcessError(Exception):
    def __init__(self, stderr: str | bytes):
        self.stderr = stderr

    def __str__(self) -> str:
        return f"stderr:\n{self.stderr}"


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
            raise CalledProcessError(stderr=tmp_f.read()) from e

        finally:
            if original_stderr is not None:
                _ = tmp_f.seek(0)
                shutil.copyfileobj(tmp_f, original_stderr)
