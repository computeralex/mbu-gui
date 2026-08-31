from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import os
import pwd
from typing import Any


INSTALLED_MBU = Path("/usr/share/mbu-gui/mbu")


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


def _default_mbu_dir(environ: Mapping[str, str]) -> Path:
    env = environ.get("MBU_GUI_MBU_DIR")
    if env:
        return Path(env)
    if (INSTALLED_MBU / "mbup").exists():
        return INSTALLED_MBU
    return Path(__file__).resolve().parents[2] / "vendor" / "mbu"


def resolve_paths(
    *,
    home: Path | None = None,
    mbu_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> MbuPaths:
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    mbu_dir = _default_mbu_dir(environ) if mbu_dir is None else mbu_dir
    state_dir = home / ".local/share/mbu-gui"
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
    )


def home_for_helper(
    *,
    environ: Mapping[str, str],
    getpwuid: Callable[[int], Any] | None = None,
) -> Path:
    getpwuid = pwd.getpwuid if getpwuid is None else getpwuid
    uid_s = environ.get("PKEXEC_UID")
    if uid_s:
        return Path(getpwuid(int(uid_s)).pw_dir)
    if environ.get("HOME"):
        return Path(environ["HOME"])
    return Path.home()
