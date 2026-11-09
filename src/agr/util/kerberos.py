"""Kerberos ticket check and automatic renewal for long pipeline runs.

The database steps (gquery imports, geno_import) authenticate with the user's
Kerberos ticket, and they come at the *end* of a run. A ticket lasts 10 hours, but a
run launched ahead of a slow copy can wait up to 24 h before it even starts, so
without renewal the run fails at its last steps.

`kinit -R` renews the existing ticket by presenting it to the KDC. It needs no
password, but only works while the ticket is still valid and before its "renew until"
time. A ticket is renewable only if it was obtained with `kinit -r <lifetime>`; the
README tells users to launch with `kinit -r 7d`.

`klist`/`kinit` being absent (e.g. a laptop) only logs a warning, so nothing that
imports the pipeline needs Kerberos to exist.
"""

import logging
import re
import shutil
import subprocess
import threading

logger = logging.getLogger(__name__)

RENEW_INTERVAL_S = 60 * 60


class KerberosError(Exception):
    pass


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    # stdin closed: a kinit that unexpectedly wanted a password fails, never blocks.
    return subprocess.run(
        args, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False
    )


def _tgt_status() -> tuple[str | None, str | None]:
    """`(expires, renew_until)` of the default principal's own TGT, from `klist -f`.

    `renew_until` is None when the ticket is not renewable (no `R` flag).
    """
    listing = _run(["klist", "-f"]).stdout
    principal = re.search(r"Default principal: \S+@(\S+)", listing)
    if principal is None:
        return None, None
    tgt = "krbtgt/{0}@{0}".format(principal.group(1))
    lines = listing.splitlines()
    for i, line in enumerate(lines):
        if tgt not in line:
            continue
        fields = line.split()
        expires = " ".join(fields[2:4])
        for detail in lines[i + 1 : i + 3]:
            if (flags := re.search(r"Flags: (\S+)", detail)) is not None:
                if "R" not in flags.group(1):
                    return expires, None
                until = re.search(r"renew until (\S+ \S+?),", detail)
                return expires, until.group(1) if until else "?"
        return expires, None
    return None, None


def check_ticket():
    """Refuse to start without a valid ticket; warn if it cannot be renewed."""
    if shutil.which("klist") is None:
        logger.warning("klist not found: not checking for a Kerberos ticket")
        return
    if _run(["klist", "-s"]).returncode != 0:
        raise KerberosError(
            "no valid Kerberos ticket, and the database steps need one: run "
            "`kinit -r 7d` and relaunch"
        )
    expires, renew_until = _tgt_status()
    if renew_until is None:
        logger.warning(
            "Kerberos ticket expires %s and is not renewable: database steps after "
            "then will fail. For a long run, `kinit -r 7d` and relaunch.",
            expires,
        )
    else:
        logger.info(
            "Kerberos ticket valid until %s, renewable until %s; renewing every %d min",
            expires,
            renew_until,
            RENEW_INTERVAL_S // 60,
        )


def renew_once() -> bool:
    """Renew the ticket with `kinit -R`, which needs no password. True on success."""
    if shutil.which("kinit") is None:
        return False
    result = _run(["kinit", "-R"])
    if result.returncode != 0:
        logger.warning(
            "Kerberos ticket renewal failed (kinit -R exit %d): %s",
            result.returncode,
            result.stderr.strip(),
        )
        return False
    logger.info("Kerberos ticket renewed, now valid until %s", _tgt_status()[0])
    return True


_renewer: threading.Thread | None = None
_stop = threading.Event()
_lock = threading.Lock()


def start_renewer(interval_s: float = RENEW_INTERVAL_S) -> threading.Thread | None:
    """Renew the ticket every `interval_s` from a daemon thread, for the life of this
    process. Started once per process; later calls return the running thread."""
    global _renewer
    if shutil.which("kinit") is None:
        logger.warning("kinit not found: not renewing the Kerberos ticket")
        return None
    with _lock:
        if _renewer is None or not _renewer.is_alive():
            _stop.clear()

            def renew_until_stopped():
                while not _stop.wait(interval_s):
                    _ = renew_once()

            _renewer = threading.Thread(
                target=renew_until_stopped, name="kerberos-renewer", daemon=True
            )
            _renewer.start()
        return _renewer


def stop_renewer(timeout_s: float = 10):
    """Stop the renewer thread, waiting for any renewal in flight to finish."""
    global _renewer
    with _lock:
        _stop.set()
        if _renewer is not None:
            _renewer.join(timeout_s)
        _renewer = None
