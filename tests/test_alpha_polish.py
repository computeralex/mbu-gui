import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtWidgets import QApplication

from mbu_gui.about_dialog import AboutDialog
from mbu_gui.disks import describe_backup_route, load_lsblk
from mbu_gui.main_window import UNPLUG_UNFINISHED_TEXT, MainWindow
from mbu_gui.version import __version__

FIXTURES = Path(__file__).parent / "fixtures"
_app = None


def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app


def test_home_shows_versions():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    text = w.versionLabel.text()
    assert __version__ in text
    assert "MBU GUI" in text
    assert "MBU" in text


def test_about_dialog_lists_both_versions(tmp_path: Path):
    app()
    (tmp_path / "mbu-README.txt").write_text(
        "# MBU Release mbu-20251115\n", encoding="utf-8"
    )
    dialog = AboutDialog(mbu_dir=tmp_path)
    assert __version__ in dialog.guiVersionLabel.text()
    assert "mbu-20251115" in dialog.mbuVersionLabel.text()


def test_unfinished_banner_mentions_partial_clone():
    lower = UNPLUG_UNFINISHED_TEXT.lower()
    assert "partial clone" in lower
    assert "unplug" in lower


def test_backup_route_says_running_system():
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    route = describe_backup_route(inv)
    assert route is not None
    assert "running system" in route
    assert "this computer" not in route
