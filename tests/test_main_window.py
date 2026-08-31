# tests/test_main_window.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from PySide6.QtWidgets import QApplication

from mbu_gui.disks import load_lsblk
from mbu_gui.logs import parse_master_log
from mbu_gui.main_window import MainWindow

FIXTURES = Path(__file__).parent / "fixtures"
_app = None


def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app


def test_window_opens_with_backup_ready():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    assert w.windowTitle() == "MBU Backup"
    assert w.statusLabel.text() == "Backup disk `bak1` is connected"
    assert w.lastRunLabel.text() == "No backup yet"
    assert w.startButton.isEnabled()
    assert w.startReasonLabel.text() == ""
    assert w.unplugBanner.isHidden()


def test_start_disabled_when_unnamed():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    assert not w.startButton.isEnabled()
    assert "Set up this computer" in w.startReasonLabel.text()


def test_error_and_unplug_and_busy():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show_error("The backup command failed (exit 1).")
    assert "exit 1" in w.logView.toPlainText()
    w.show_unplug(True)
    assert not w.unplugBanner.isHidden()
    w.set_running(True)
    assert not w.startButton.isEnabled()
    assert not w.setupButton.isEnabled()
