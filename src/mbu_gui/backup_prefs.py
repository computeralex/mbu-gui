from __future__ import annotations

from pathlib import Path
import json
import os
import re
import tempfile
from collections.abc import Mapping

_SET_RE = re.compile(r"^[A-Za-z0-9]+$")


def prefs_dir(environ: Mapping[str, str] | None = None) -> Path:
    environ = os.environ if environ is None else environ
    xdg = environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "mbu-gui"
    home = environ.get("HOME") or str(Path.home())
    return Path(home) / ".config" / "mbu-gui"


def _prefs_path(set_name: str, config_dir: Path) -> Path:
    if not _SET_RE.fullmatch(set_name):
        raise ValueError(f"invalid set name for prefs: {set_name!r}")
    return config_dir / f"backup-selection-{set_name}.json"


def load_backup_selection(
    set_name: str, *, config_dir: Path | None = None
) -> dict | None:
    directory = prefs_dir() if config_dir is None else config_dir
    path = _prefs_path(set_name, directory)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    functions = data.get("functions")
    boot_fix = data.get("boot_fix")
    if not isinstance(functions, list) or not all(isinstance(x, str) for x in functions):
        return None
    if not isinstance(boot_fix, bool):
        return None
    return {"functions": list(functions), "boot_fix": boot_fix}


def save_backup_selection(
    set_name: str,
    *,
    functions: list[str],
    boot_fix: bool,
    config_dir: Path | None = None,
) -> None:
    directory = prefs_dir() if config_dir is None else config_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = _prefs_path(set_name, directory)
    payload = {"functions": list(functions), "boot_fix": boot_fix}
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=".backup-selection-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        Path(tmp_name).replace(path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
