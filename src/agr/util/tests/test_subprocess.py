import pytest
import tempfile
from agr.util.subprocess import run_catching_stderr, CalledProcessError


def test_run_catching_stderr_returncode():
    p = run_catching_stderr(
        ["echo hello-to-stdout ; echo >&2 oops-on-stderr"],
        shell=True,
        text=True,
        check=True,
    )
    assert p.returncode == 0


def test_run_catching_stderr():
    with pytest.raises(CalledProcessError) as excinfo:
        run_catching_stderr(
            ["echo hello-to-stdout ; echo >&2 oops-on-stderr ; exit 1"],
            shell=True,
            text=True,
            check=True,
        )
    assert excinfo.value.stderr == "oops-on-stderr\n"


def test_run_catching_stderr_and_saving():
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        with pytest.raises(CalledProcessError) as excinfo:
            run_catching_stderr(
                ["echo hello-to-stdout ; echo >&2 oops-on-stderr ; exit 1"],
                stderr=tmp_f,
                shell=True,
                text=True,
                check=True,
            )
        assert excinfo.value.stderr == "oops-on-stderr\n"

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
