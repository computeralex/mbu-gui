from __future__ import annotations

from dataclasses import dataclass
import re


DONE_RE = re.compile(
    r"^(?P<ts>\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}) DONE- BACKUP FROM (?P<frm>\S+) TO (?P<to>\S+) : (?P<fncs>.*)$"
)
START_RE = re.compile(
    r"^(?P<ts>\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}) START BACKUP FROM (?P<frm>\S+) TO (?P<to>\S+)\s*$"
)


@dataclass(frozen=True)
class LastRun:
    timestamp: str
    from_set: str
    to_set: str
    functions: str
    ok: bool


def parse_master_log(text: str) -> LastRun | None:
    last: LastRun | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = DONE_RE.match(line)
        if m:
            last = LastRun(
                timestamp=m.group("ts"),
                from_set=m.group("frm"),
                to_set=m.group("to"),
                functions=m.group("fncs").strip(),
                ok=True,
            )
            continue
        m = START_RE.match(line)
        if m:
            last = LastRun(
                timestamp=m.group("ts"),
                from_set=m.group("frm"),
                to_set=m.group("to"),
                functions="",
                ok=False,
            )
    return last


def last_run_label(run: LastRun | None) -> str:
    if run is None:
        return "No backup yet"
    label = f"Last backup: {run.timestamp}  {run.from_set} → {run.to_set}"
    if not run.ok:
        label += " (failed)"
    return label


_RENAMED_RE = re.compile(
    r"^Partition name changed from '(?P<old>[^']*)' to '(?P<new>[^']*)'\.$"
)

# sfdisk narrates every step of rewriting a partition table. None of it means
# anything to someone who just wants a backup, and the "busy" pair reads like a
# failure when it is the normal result of renaming the disk you booted from.
_SFDISK_CHATTER = (
    "The partition table has been altered.",
    "Calling ioctl() to re-read partition table.",
    "Syncing disks.",
)
_SFDISK_BUSY = (
    "Re-reading the partition table failed",
    "The kernel still uses the old table",
)


def plain_label_line(line: str) -> str | None:
    """Rewrite one line of sfdisk output for a non-expert, or drop it.

    Returns None for lines that should not be shown at all. Anything we do not
    recognise is passed through untouched, so a real error is never swallowed.
    """
    s = line.strip()
    if not s:
        return None
    if s in _SFDISK_CHATTER or s.startswith(_SFDISK_BUSY):
        return None
    m = _RENAMED_RE.match(s)
    if m:
        return f"Named this computer's {m.group('new')} partition"
    return line


def current_file_from_line(line: str) -> str | None:
    s = line.strip()
    if not s:
        return None
    if s.startswith("sent ") or "total size" in s:
        return None
    if s.endswith("/"):
        return None
    if "START " in s or "DONE " in s:
        return None
    if "/" in s or s.startswith("."):
        return s
    return None
