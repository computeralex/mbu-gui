from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from mbu_gui.app import create_app
from mbu_gui.desktop_icon import maybe_install_desktop_icon
from mbu_gui.disks import Inventory, load_lsblk
from mbu_gui.helper_client import which_helper
from mbu_gui.logs import parse_master_log
from mbu_gui.main_window import MainWindow
from mbu_gui.paths import resolve_paths

_INSTALLED_DESKTOP = Path("/usr/share/applications/mbu-gui.desktop")
_REPO_DESKTOP = Path(__file__).resolve().parents[2] / "data" / "mbu-gui.desktop"

_LSBLK_COLUMNS = "NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINT,PARTLABEL,PARTN,UUID,MODEL"


def load_inventory() -> Inventory:
    out = subprocess.check_output(
        ["lsblk", "-J", "-o", _LSBLK_COLUMNS],
        text=True,
    )
    return load_lsblk(out)


def main() -> int:
    app = create_app(sys.argv)
    paths = resolve_paths()
    err = None
    try:
        inv = load_inventory()
    except Exception as e:
        inv = Inventory.empty(str(e))
        err = str(e)
    last = None
    if paths.master_log.exists():
        last = parse_master_log(paths.master_log.read_text(errors="replace"))
    w = MainWindow(
        inventory=inv,
        last_run=last,
        reload_inventory=load_inventory,
        helper_exists=bool(which_helper()),
        pkexec_exists=bool(shutil.which("pkexec")),
    )
    if err:
        w.show_error(err)
    w.show()
    source = _INSTALLED_DESKTOP if _INSTALLED_DESKTOP.exists() else _REPO_DESKTOP
    maybe_install_desktop_icon(desktop_dir=Path.home() / "Desktop", source=source)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
