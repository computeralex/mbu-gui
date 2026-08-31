# tests/test_browse_page.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from mbu_gui.disks import load_lsblk
from mbu_gui.browse_page import BrowsePage
from mbu_gui.helper_client import failed_command_message
from mbu_gui.main_window import PAGE_BROWSE, PAGE_HOME, MainWindow
from mbu_gui.paths import resolve_paths

FIXTURES = Path(__file__).parent / "fixtures"
_app = None
def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app

def test_browse_lists_backup_sets():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = BrowsePage(inv)
    assert p.setList.count() == 1
    assert p.setList.item(0).text() == "bak1"


def test_unmount_failure_does_not_unplug():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, helper_exists=True, pkexec_exists=True, start_process=lambda argv: None, helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"))
    w.on_unmount_finished(1)
    assert "Could not unmount" in w.browsePage.busyLabel.text()
    assert w.unplugBanner.isHidden()
    w.on_unmount_finished(0)
    assert not w.unplugBanner.isHidden()


UNMOUNT_FAIL_TEXT = (
    "Could not unmount. Close the file manager, click away from those folders, then try Unmount again."
)


def _window(inv, **kwargs):
    kwargs.setdefault("last_run", None)
    kwargs.setdefault("helper_exists", True)
    kwargs.setdefault("pkexec_exists", True)
    kwargs.setdefault("start_process", lambda argv: None)
    kwargs.setdefault("helper_path", Path("/usr/lib/mbu-gui/mbu-gui-helper"))
    return MainWindow(inventory=inv, **kwargs)


def test_open_disabled_until_mounted():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = BrowsePage(inv)
    assert p.mounted is False
    assert not p.openButton.isEnabled()
    assert not p.unmountButton.isEnabled()
    p.setList.setCurrentRow(0)
    p._sync_enabled()
    assert p.mountButton.isEnabled()
    p.set_mounted(True)
    assert p.openButton.isEnabled()
    assert p.unmountButton.isEnabled()
    assert not p.mountButton.isEnabled()


def test_no_backup_sets_disables_mount():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    p = BrowsePage(inv)
    assert p.setList.count() == 0
    assert not p.mountButton.isEnabled()
    assert p.busyLabel.text() == "Plug in the backup disk"


def test_two_sets_listed():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_two_backups.json").read_text())
    p = BrowsePage(inv)
    names = [p.setList.item(i).text() for i in range(p.setList.count())]
    assert names == ["bak1", "bak2"]
    assert not p.mountButton.isEnabled()
    p.setList.setCurrentRow(1)
    p._sync_enabled()
    assert p.mountButton.isEnabled()
    assert p.selected_set_name() == "bak2"


def test_browse_button_shows_browse_page():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    assert w.stack.currentIndex() == PAGE_HOME
    assert w.stack.indexOf(w.browsePage) == PAGE_BROWSE
    w.browseButton.click()
    assert w.stack.currentIndex() == PAGE_BROWSE


def test_leave_returns_home_without_helper():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    calls = []
    w = _window(inv, start_process=lambda argv: calls.append(argv))
    w.browseButton.click()
    w.browsePage.leaveButton.click()
    assert w.stack.currentIndex() == PAGE_HOME
    assert calls == []


def test_mount_runs_mount_set():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    captured = []
    w = _window(inv, start_process=lambda argv: captured.append(argv))
    w.browseButton.click()
    w.browsePage.setList.setCurrentRow(0)
    w.browsePage._sync_enabled()
    w.browsePage.mountButton.click()
    assert captured == [[
        "pkexec",
        "/usr/lib/mbu-gui/mbu-gui-helper",
        "mount",
        "--set",
        "bak1",
    ]]


def test_mount_success_enables_open():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _window(inv)
    w.browseButton.click()
    w.browsePage.setList.setCurrentRow(0)
    w.browsePage.mountButton.click()
    w.on_mount_finished(0)
    assert w.browsePage.mounted is True
    assert w.browsePage.openButton.isEnabled()
    assert w.browsePage.unmountButton.isEnabled()
    assert w.unplugBanner.isHidden()
    assert w.stack.currentIndex() == PAGE_BROWSE


def test_mount_failure_no_unplug():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _window(inv)
    w.browseButton.click()
    w.browsePage.setList.setCurrentRow(0)
    w.browsePage.mountButton.click()
    w.on_mount_finished(1)
    assert failed_command_message(1, "mount") in w.logView.toPlainText()
    assert w.browsePage.mounted is False
    assert not w.browsePage.openButton.isEnabled()
    assert w.unplugBanner.isHidden()


def test_open_uses_open_dir():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    opened = []
    mount_dir = Path("/tmp/mbu-gui-test-mount")
    w = _window(inv, open_dir=lambda path: opened.append(path))
    w.browsePage.mount_dir = mount_dir
    w.browsePage.set_mounted(True)
    w.browsePage.openButton.click()
    assert opened == [str(mount_dir)]


def test_open_xdg_open_default(monkeypatch):
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    calls = []

    def fake_popen(argv, *args, **kwargs):
        calls.append(list(argv))
        class Proc:
            pass
        return Proc()

    monkeypatch.setattr("mbu_gui.browse_page.subprocess.Popen", fake_popen)
    p = BrowsePage(inv, mount_dir=Path("/tmp/mbu-gui-test-mount"))
    p.open_mount_dir()
    assert calls == [["xdg-open", "/tmp/mbu-gui-test-mount"]]


def test_open_default_uses_paths_mount_dir(monkeypatch):
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    calls = []

    def fake_popen(argv, *args, **kwargs):
        calls.append(list(argv))
        class Proc:
            pass
        return Proc()

    monkeypatch.setattr("mbu_gui.browse_page.subprocess.Popen", fake_popen)
    p = BrowsePage(inv)
    p.open_mount_dir()
    assert calls == [["xdg-open", str(resolve_paths().mount_dir)]]


def test_open_failure_shows_error():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())

    def boom(_path):
        raise FileNotFoundError("No such file or directory: 'xdg-open'")

    w = _window(inv, open_dir=boom)
    w.browsePage.set_mounted(True)
    w.browsePage.openButton.click()
    assert "xdg-open" in w.logView.toPlainText()


def test_unmount_runs_clean():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    captured = []
    w = _window(inv, start_process=lambda argv: captured.append(argv))
    w.browseButton.click()
    w.browsePage.setList.setCurrentRow(0)
    w.browsePage.mountButton.click()
    w.on_mount_finished(0)
    captured.clear()
    w.browsePage.unmountButton.click()
    assert captured == [[
        "pkexec",
        "/usr/lib/mbu-gui/mbu-gui-helper",
        "clean",
    ]]


def test_unmount_failure_exact_copy_and_retry():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _window(inv)
    w.browseButton.click()
    w.browsePage.setList.setCurrentRow(0)
    w.browsePage.mountButton.click()
    w.on_mount_finished(0)
    w.browsePage.unmountButton.click()
    w.on_unmount_finished(1)
    assert w.browsePage.busyLabel.text() == UNMOUNT_FAIL_TEXT
    assert w.unplugBanner.isHidden()
    assert w.stack.currentIndex() == PAGE_BROWSE
    assert w.browsePage.mounted is True
    assert w.browsePage.unmountButton.isEnabled()


def test_unmount_success_unplug_and_home():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _window(inv)
    w.browseButton.click()
    w.browsePage.setList.setCurrentRow(0)
    w.browsePage.mountButton.click()
    w.on_mount_finished(0)
    w.browsePage.unmountButton.click()
    w.on_unmount_finished(0)
    assert not w.unplugBanner.isHidden()
    assert w.stack.currentIndex() == PAGE_HOME
    assert w.browsePage.mounted is False


def test_missing_helper_does_not_mount():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    calls = []
    w = _window(
        inv,
        helper_exists=False,
        helper_path=None,
        start_process=lambda argv: calls.append(argv),
    )
    w.browseButton.click()
    w.browsePage.setList.setCurrentRow(0)
    w.browsePage._sync_enabled()
    w.browsePage.mountButton.click()
    assert calls == []
    assert "not installed" in w.logView.toPlainText().lower()
    assert w.unplugBanner.isHidden()
    assert w.browsePage.mounted is False
