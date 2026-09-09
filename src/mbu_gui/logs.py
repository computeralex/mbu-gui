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


SYNC_START_RE = re.compile(r"^START Directory SYNC FROM (?P<frm>\S+) TO (?P<to>\S+)")


def sync_target(line: str) -> str | None:
    """Name of the thing MBU just started copying, or None for other lines.

    MBU announces each partition it syncs. rsync itself is run without
    --info=progress2, so there are no byte totals to read; these markers are
    the only honest progress signal available without changing MBU.
    """
    m = SYNC_START_RE.match(line.strip())
    if m is None:
        return None
    dest = m.group("to").rstrip("/")
    return dest.rsplit("/", 1)[-1] or dest


def progress_label(done: int, total: int, target: str, files: int) -> str:
    where = f"Copying {target}" if target else "Copying"
    step = f"{where} ({done} of {total})" if total else where
    if files:
        return f"{step} — {files:,} files so far"
    return step


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


_ANSI_RE = re.compile(
    r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"  # ECMA-48 CSI / single-char
    r"|\[(?:\d{1,3};)*\d{0,3}m"  # leftover SGR after ESC was stripped
)
_TOTAL_SIZE_RE = re.compile(r"total size is\s+([0-9,]+)", re.IGNORECASE)
_ROUTE_RE = re.compile(
    r"(?:START BACKUP FROM|DONE-\s*BACKUP FROM|BACKING UP PARTITION SET) "
    r"(?P<frm>\S+) TO (?P<to>\S+)"
)
_DIAG_LINE_RE = re.compile(r"\w+:\d+")
_NOT_A_FILE_RE = re.compile(
    r"\b(?:START|DONE-?|Status|FINISHED|BACKUP FROM|BACKING UP)\b"
)


def strip_ansi(text: str) -> str:
    """Remove MBU/rsync colour codes, including orphan [32m leftovers."""
    return _ANSI_RE.sub("", text)


def current_file_from_line(line: str) -> str | None:
    s = strip_ansi(line).strip()
    if not s:
        return None
    if s.startswith("sent ") or "total size" in s:
        return None
    if s.endswith("/"):
        return None
    if _NOT_A_FILE_RE.search(s) or _DIAG_LINE_RE.search(s):
        return None
    if s.lower().startswith("mbuclean"):
        return None
    if " removed " in s:
        return None
    if "/" in s or s.startswith("."):
        return s
    return None


def parse_total_size_bytes(line: str) -> int | None:
    m = _TOTAL_SIZE_RE.search(strip_ansi(line))
    if m is None:
        return None
    return int(m.group(1).replace(",", ""))


def copied_bytes_from_lines(lines: list[str]) -> int | None:
    """Sum rsync 'total size is' lines. None if MBU never printed one."""
    total = 0
    found = False
    for line in lines:
        n = parse_total_size_bytes(line)
        if n is None:
            continue
        total += n
        found = True
    return total if found else None


def route_sets_from_lines(lines: list[str]) -> tuple[str, str] | None:
    last: tuple[str, str] | None = None
    for raw in lines:
        m = _ROUTE_RE.search(strip_ansi(raw))
        if m:
            last = (m.group("frm"), m.group("to"))
    return last


def format_copied_size(n: int) -> str:
    gib = 1024 ** 3
    mib = 1024 ** 2
    kib = 1024
    if n >= gib:
        value = n / gib
        if value >= 10:
            return f"about {value:.0f} GB"
        pretty = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"about {pretty} GB"
    if n >= mib:
        return f"about {n / mib:.0f} MB"
    if n >= kib:
        return f"about {n / kib:.0f} KB"
    return f"about {n} bytes"


def backup_summary(
    *,
    from_set: str | None,
    to_set: str | None,
    copied_bytes: int | None,
) -> str:
    if from_set and to_set:
        route = f"from this computer ({from_set}) onto {to_set}"
    elif to_set:
        route = f"from this computer onto {to_set}"
    elif from_set:
        route = f"from this computer ({from_set}) onto the backup disk"
    else:
        route = "from this computer onto the backup disk"
    if copied_bytes is not None:
        return f"Copied {format_copied_size(copied_bytes)} {route}."
    return f"Copied {route}."
