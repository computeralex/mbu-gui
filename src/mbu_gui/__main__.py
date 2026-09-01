from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from mbu_gui.disks import Inventory, load_lsblk
from mbu_gui.helper_client import which_helper
from mbu_gui.logs import LastRun, parse_master_log
from mbu_gui.machine import apply_machine_guard, load_machine_record, record_path
from mbu_gui.paths import resolve_paths

_INSTALLED_DESKTOP = Path("/usr/share/applications/mbu-gui.desktop")
_REPO_DESKTOP = Path(__file__).resolve().parents[2] / "data" / "mbu-gui.desktop"

_LSBLK_COLUMNS = (
    "NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINT,PARTLABEL,PARTN,UUID,MODEL,SERIAL,WWN,PTUUID"
)


def load_inventory() -> Inventory:
    out = subprocess.check_output(
        ["lsblk", "-J", "-o", _LSBLK_COLUMNS],
        text=True,
    )
    inventory = load_lsblk(out)
    record = load_machine_record(record_path(resolve_paths().state_dir))
    return apply_machine_guard(inventory, record)


def load_last_run() -> LastRun | None:
    paths = resolve_paths()
    if not paths.master_log.exists():
        return None
    return parse_master_log(paths.master_log.read_text(errors="replace"))


def backup_unfinished() -> bool:
    """True when a previous backup never finished cleanly, even across a crash."""
    return resolve_paths().incomplete_marker.exists()


def main() -> int:
    try:
        from mbu_gui.app import create_app
        from mbu_gui.desktop_icon import maybe_install_desktop_icon
        from mbu_gui.main_window import MainWindow
    except ImportError as e:
        from mbu_gui.missing_pyside import handle_import_error

        return handle_import_error(e)

    app = create_app(sys.argv)
    err = None
    try:
        inv = load_inventory()
    except Exception as e:
        inv = Inventory.empty(str(e))
        err = str(e)
    last = load_last_run()
    w = MainWindow(
        inventory=inv,
        last_run=last,
        reload_inventory=load_inventory,
        reload_last_run=load_last_run,
        helper_exists=bool(which_helper()),
        pkexec_exists=bool(shutil.which("pkexec")),
        backup_unfinished=backup_unfinished(),
    )
    if err:
        w.show_error(err)
    w.show()
    source = _INSTALLED_DESKTOP if _INSTALLED_DESKTOP.exists() else _REPO_DESKTOP
    maybe_install_desktop_icon(desktop_dir=Path.home() / "Desktop", source=source)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
