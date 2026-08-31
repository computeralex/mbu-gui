from __future__ import annotations

import subprocess
import sys

from mbu_gui.app import create_app
from mbu_gui.disks import Inventory, load_lsblk
from mbu_gui.logs import parse_master_log
from mbu_gui.main_window import MainWindow
from mbu_gui.paths import resolve_paths

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
    w = MainWindow(inventory=inv, last_run=last, reload_inventory=load_inventory)
    if err:
        w.show_error(err)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
