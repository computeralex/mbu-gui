from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import os


INSTALLED_MBU = Path("/usr/share/mbu-gui/mbu")

# Root writes MBU's logs, generated format tables and mount points here.
# It must NOT be under any user's home: the helper runs as root, and a
# user-writable path lets the caller redirect root's writes through a symlink
# or swap a format table out from under root between generating and using it.
STATE_DIR = Path("/var/lib/mbu-gui")


@dataclass(frozen=True)
class MbuPaths:
    mbu_dir: Path
    state_dir: Path
    log_dir: Path
    out_dir: Path
    mount_dir: Path
    master_log: Path
    backup_latest_log: Path
    format_latest_log: Path
    incomplete_marker: Path


def _default_mbu_dir(environ: Mapping[str, str]) -> Path:
    env = environ.get("MBU_GUI_MBU_DIR")
    if env:
        return Path(env)
    if (INSTALLED_MBU / "mbup").exists():
        return INSTALLED_MBU
    return Path(__file__).resolve().parents[2] / "vendor" / "mbu"


def resolve_paths(
    *,
    state_dir: Path | None = None,
    mbu_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> MbuPaths:
    environ = os.environ if environ is None else environ
    mbu_dir = _default_mbu_dir(environ) if mbu_dir is None else mbu_dir
    state_dir = STATE_DIR if state_dir is None else state_dir
    log_dir = state_dir / "log"
    out_dir = state_dir / "out"
    mount_dir = state_dir / "mount"
    return MbuPaths(
        mbu_dir=mbu_dir,
        state_dir=state_dir,
        log_dir=log_dir,
        out_dir=out_dir,
        mount_dir=mount_dir,
        master_log=log_dir / "mbu.log",
        backup_latest_log=log_dir / "mbup-latest.log",
        format_latest_log=log_dir / "mbuformat-latest.log",
        # Present from the moment a backup starts until one finishes cleanly, so
        # a crash or a killed GUI still leaves evidence that MBU may have
        # already cloned filesystem UUIDs onto the backup disk.
        incomplete_marker=state_dir / "backup-incomplete",
    )
