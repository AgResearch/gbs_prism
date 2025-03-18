import io
import shutil
import subprocess
import tempfile


class CalledProcessError(Exception):
    def __init__(self, stderr: str | bytes, returncode: int = 0, cmd: list[str] = []):
        """To avoid showing as Unknown in redun console, the constructor must have only one parameter without default value."""
        self.stderr = stderr
        self.returncode = returncode
        self.cmd = cmd
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"Command `{' '.join(self.cmd)}` failed with exit status {self.returncode}\n{self.stderr}"


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
            raise CalledProcessError(
                stderr=tmp_f.read(), returncode=e.returncode, cmd=e.cmd
            ) from e

        finally:
            if original_stderr is not None:
                _ = tmp_f.seek(0)
                shutil.copyfileobj(tmp_f, original_stderr)
