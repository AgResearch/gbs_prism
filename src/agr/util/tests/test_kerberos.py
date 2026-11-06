"""Tests for the Kerberos ticket check and renewal.

`klist` and `kinit` are replaced by tiny shell scripts on a private PATH, so these
run anywhere and never touch a real credential cache.
"""

import logging
import os
import stat

import pytest

from agr.util import kerberos
from agr.util.kerberos import KerberosError, check_ticket, renew_once

RENEWABLE = """\
Ticket cache: KEYRING:persistent:1:1
Default principal: someone@AGRESEARCH.CO.NZ

Valid starting     Expires            Service principal
11/06/26 11:56:52  11/06/26 21:56:24  postgres/db.example@IAM.FLEXI.NESI.ORG.NZ
\trenew until 11/13/26 11:56:18, Flags: FRAT
11/06/26 11:56:24  11/06/26 21:56:24  krbtgt/AGRESEARCH.CO.NZ@AGRESEARCH.CO.NZ
\trenew until 11/13/26 11:56:18, Flags: FRIA
"""

NOT_RENEWABLE = """\
Ticket cache: KEYRING:persistent:1:1
Default principal: someone@AGRESEARCH.CO.NZ

Valid starting     Expires            Service principal
11/06/26 11:56:24  11/06/26 21:56:24  krbtgt/AGRESEARCH.CO.NZ@AGRESEARCH.CO.NZ
\tFlags: FIA
"""


def _script(bin_dir, name, body):
    path = bin_dir / name
    _ = path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def fake_bin(tmp_path, monkeypatch):
    """A PATH holding only the fake tools each test writes."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))
    return bin_dir


def _klist(bin_dir, listing, valid=True):
    listing_file = bin_dir / "listing.txt"
    _ = listing_file.write_text(listing)
    _script(
        bin_dir,
        "klist",
        # Builtins only: the PATH holds nothing else.
        '[ "$1" = "-s" ] && exit %d\nwhile IFS= read -r line; do printf "%%s\\n" "$line"; done < %s\n'
        % (0 if valid else 1, listing_file),
    )


def test_check_ticket_refuses_to_start_without_a_valid_ticket(fake_bin):
    _klist(fake_bin, "", valid=False)
    with pytest.raises(KerberosError, match="kinit -r 7d"):
        check_ticket()


def test_check_ticket_accepts_a_renewable_ticket(fake_bin, caplog):
    _klist(fake_bin, RENEWABLE)
    with caplog.at_level(logging.INFO, logger="agr.util.kerberos"):
        check_ticket()
    assert "valid until 11/06/26 21:56:24, renewable until 11/13/26 11:56:18" in caplog.text
    assert "not renewable" not in caplog.text


def test_check_ticket_warns_when_the_ticket_cannot_be_renewed(fake_bin, caplog):
    """Not fatal: a short, cached rerun can finish inside the ticket's lifetime."""
    _klist(fake_bin, NOT_RENEWABLE)
    with caplog.at_level(logging.WARNING, logger="agr.util.kerberos"):
        check_ticket()
    assert "expires 11/06/26 21:56:24 and is not renewable" in caplog.text
    assert "kinit -r 7d" in caplog.text


def test_check_ticket_only_warns_where_there_is_no_kerberos(fake_bin, caplog):
    with caplog.at_level(logging.WARNING, logger="agr.util.kerberos"):
        check_ticket()
    assert "klist not found" in caplog.text


def test_renew_once_runs_kinit_minus_r_without_a_password(fake_bin, tmp_path):
    _klist(fake_bin, RENEWABLE)
    args_file = tmp_path / "kinit-args"
    # No stdin: a kinit that wanted a password would fail rather than block.
    _script(fake_bin, "kinit", 'echo "$@" > %s\n' % args_file)
    assert renew_once()
    assert args_file.read_text().strip() == "-R"


def test_renew_once_reports_a_failed_renewal(fake_bin, caplog):
    _script(fake_bin, "kinit", "echo 'kinit: Ticket expired while renewing credentials' >&2\nexit 1\n")
    with caplog.at_level(logging.WARNING, logger="agr.util.kerberos"):
        assert not renew_once()
    assert "Ticket expired while renewing credentials" in caplog.text


def test_renew_once_without_kinit_is_false(fake_bin):
    assert not renew_once()


@pytest.fixture
def no_renewer(monkeypatch):
    """A fresh renewer slot, stopped afterwards: a thread left running would call the
    real `kinit -R` once the PATH is restored."""
    monkeypatch.setattr(kerberos, "_renewer", None)
    yield
    kerberos.stop_renewer()


def test_start_renewer_starts_one_daemon_thread_per_process(fake_bin, no_renewer):
    _script(fake_bin, "kinit", "exit 0\n")
    first = kerberos.start_renewer(interval_s=3600)
    second = kerberos.start_renewer(interval_s=3600)
    assert first is not None and first is second
    assert first.daemon and first.is_alive()
    kerberos.stop_renewer()
    first.join(5)
    assert not first.is_alive()


def test_start_renewer_renews_every_interval(fake_bin, tmp_path, no_renewer):
    count_file = tmp_path / "renewals"
    _script(fake_bin, "kinit", "echo x >> %s\n" % count_file)
    _klist(fake_bin, RENEWABLE)
    thread = kerberos.start_renewer(interval_s=0.05)
    assert thread is not None
    for _ in range(100):
        if os.path.exists(count_file) and len(count_file.read_text().split()) >= 2:
            break
        thread.join(0.05)
    assert len(count_file.read_text().split()) >= 2
