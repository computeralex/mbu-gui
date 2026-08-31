from __future__ import annotations

from pathlib import Path
import shutil


def maybe_install_desktop_icon(*, desktop_dir: Path, source: Path) -> None:
    dest = desktop_dir / "mbu-gui.desktop"
    if not desktop_dir.exists() or dest.exists():
        return
    try:
        shutil.copy(source, dest)
    except OSError:
        return
