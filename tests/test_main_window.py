# tests/test_main_window.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from mbu_gui.disks import load_lsblk
from mbu_gui.logs import LastRun
from mbu_gui.main_window import PAGE_FORMAT, PAGE_HOME, PAGE_SETUP, MainWindow, _icon_candidates

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


def test_log_and_banner_stay_visible_off_home():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    w.append_log("formatting...")
    w.formatButton.click()
    assert w.stack.currentIndex() == PAGE_FORMAT
    assert w.stack.indexOf(w.logView) == -1
    assert not w.logView.isHidden()
    assert "formatting..." in w.logView.toPlainText()
    assert not w.currentFileLabel.isHidden()
    w.show_unplug(True)
    assert not w.unplugBanner.isHidden()


def test_icon_candidates_include_installed_and_repo_paths():
    paths = [str(p) for p in _icon_candidates()]
    assert "/usr/share/mbu-gui/mbu-icon.png" in paths
    assert any(p.endswith("/data/mbu-icon.png") for p in paths)


def test_close_ignored_while_running():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    w.set_running(True)
    event = QCloseEvent()
    w.closeEvent(event)
    assert not event.isAccepted()
    assert w.isVisible()


def test_close_refused_while_browse_mounted():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    w.browsePage.set_mounted(True)
    event = QCloseEvent()
    w.closeEvent(event)
    assert not event.isAccepted()
    assert "Unmount" in w.logView.toPlainText()


def test_refresh_after_backup_and_when_returning_home():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    unnamed = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    last = LastRun(
        timestamp="2026/08/31-12:00:00",
        from_set="main",
        to_set="bak1",
        functions="root",
        ok=True,
    )
    counts = {"inv": 0, "last": 0}

    def reload_inventory():
        counts["inv"] += 1
        return unnamed if counts["inv"] == 1 else inv

    def reload_last_run():
        counts["last"] += 1
        return last

    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: None,
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
        reload_inventory=reload_inventory,
        reload_last_run=reload_last_run,
    )
    w._run_backup_with_fselection("root")
    w.on_helper_finished(0)
    assert counts["inv"] >= 1
    assert counts["last"] >= 1
    assert "2026/08/31-12:00:00" in w.lastRunLabel.text()
    assert w.statusLabel.text() == unnamed.status_line

    before = dict(counts)
    w.setupButton.click()
    assert w.stack.currentIndex() == PAGE_SETUP
    w.setupPage.leaveButton.click()
    assert w.stack.currentIndex() == PAGE_HOME
    assert counts["inv"] > before["inv"]
    assert counts["last"] > before["last"]
    assert w._refresh_timer.interval() == 2000
