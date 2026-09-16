from __future__ import annotations

from pathlib import Path
import re

__version__ = "0.1.0-alpha.6"

_RELEASE_RE = re.compile(r"^#\s*MBU Release\s+(mbu-\d{8})\s*$", re.MULTILINE)
_CANDIDATES = ("mbu-README.txt", "README.md")


def read_mbu_release(mbu_dir: Path) -> str:
    """Return the vendored MBU release id, e.g. mbu-20251115."""
    for name in _CANDIDATES:
        path = mbu_dir / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = _RELEASE_RE.search(text)
        if match:
            return match.group(1)
    return "unknown"
