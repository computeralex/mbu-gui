from __future__ import annotations

import json
import os
import signal
from pathlib import Path

no_run_text = "No backup is running."
stale_run_text = "The backup has already stopped."
reused_pid_text = "Refusing to stop a process that is not the backup we started."

# Field 22 of /proc/<pid>/stat, counted from after the command name. The name is
# wrapped in brackets and may itself contain spaces and brackets, so everything
# before the last ") " has to go before the fields can be counted.
_STARTTIME_INDEX = 19


def start_ticks(pid: int, proc_root: Path = Path("/proc")) -> int | None:
    """When a process started, in clock ticks since boot.

    A pid on its own is not proof of identity: the backup can finish and the
    number be handed to something else before anyone presses Cancel. The start
    time makes that reuse detectable.
    """
    try:
        stat = (proc_root / str(pid) / "stat").read_text()
    except OSError:
        return None
    fields = stat.rsplit(") ", 1)[-1].split()
    try:
        return int(fields[_STARTTIME_INDEX])
    except (IndexError, ValueError):
        return None


def record_run(path: Path, pgid: int, *, proc_root: Path = Path("/proc")) -> None:
    path.write_text(
        json.dumps({"pgid": pgid, "start": start_ticks(pgid, proc_root)}) + "\n"
    )


def clear_run(path: Path) -> None:
    path.unlink(missing_ok=True)


def read_run(path: Path) -> dict | None:
    try:
        record = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def cancel_run(
    path: Path,
    *,
    proc_root: Path = Path("/proc"),
    kill=os.killpg,
) -> str | None:
    """Stop the recorded backup. Returns a message to show, or None if stopped.

    Signalling the process group rather than one process is what makes this
    work: the helper's child is bash, and the copying is done by rsync below it.
    """
    record = read_run(path)
    if record is None:
        return no_run_text
    pgid = record.get("pgid")
    if not isinstance(pgid, int) or pgid <= 1:
        return no_run_text
    running = start_ticks(pgid, proc_root)
    if running is None:
        return stale_run_text
    if running != record.get("start"):
        return reused_pid_text
    kill(pgid, signal.SIGTERM)
    return None
