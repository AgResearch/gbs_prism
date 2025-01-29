import pytest
import tempfile
from agr.util.subprocess import run_catching_stderr


def test_run_catching_stderr_returncode():
    p = run_catching_stderr(
        ["echo hello-to-stdout ; echo >&2 oops-on-stderr"],
        shell=True,
        text=True,
        check=True,
    )
    assert p.returncode == 0


def test_run_catching_stderr():
    cmd = "echo hello-to-stdout ; echo >&2 oops-on-stderr ; exit 1"
    with pytest.raises(Exception) as excinfo:
        run_catching_stderr(
            [cmd],
            shell=True,
            text=True,
            check=True,
        )
    assert str(excinfo.value) == f"`{cmd}` failed:\noops-on-stderr\n"


def test_run_catching_stderr_and_saving():
    cmd = "echo hello-to-stdout ; echo >&2 oops-on-stderr ; exit 1"
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        with pytest.raises(Exception) as excinfo:
            run_catching_stderr(
                [cmd],
                stderr=tmp_f,
                shell=True,
                text=True,
                check=True,
            )
        assert str(excinfo.value) == f"`{cmd}` failed:\noops-on-stderr\n"

        # check we also saved stderr
        _ = tmp_f.seek(0)
        assert tmp_f.read() == "oops-on-stderr\n"


def test_run_catching_stderr_no_error():
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        run_catching_stderr(
            ["echo hello-to-stdout ; echo >&2 all-good-on-stderr"],
            stderr=tmp_f,
            shell=True,
            text=True,
            check=True,
        )
        _ = tmp_f.seek(0)
        assert tmp_f.read() == "all-good-on-stderr\n"
