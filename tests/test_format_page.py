# tests/test_format_page.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from mbu_gui.disks import load_lsblk
from mbu_gui.format_page import FormatPage
from mbu_gui.helper_client import failed_command_message
from mbu_gui.main_window import PAGE_FORMAT, PAGE_HOME, MainWindow

FIXTURES = Path(__file__).parent / "fixtures"
_app = None
def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app

def test_format_button_requires_typed_device():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = FormatPage(inv)
    assert "erase" in p.wipeWarningLabel.text().lower()
    assert p.diskList.count() == 1
    p.diskList.setCurrentRow(0)
    p.psetEdit.setText("bak9")
    p.confirmEdit.setText("sda")  # live disk name — must NOT enable
    p._sync_enabled()
    assert not p.formatButton.isEnabled()
    p.confirmEdit.setText("sdb")
    p._sync_enabled()
    assert p.formatButton.isEnabled()
    p.psetEdit.setText("main")  # live set
    p._sync_enabled()
    assert not p.formatButton.isEnabled()


def test_wipe_warning_is_exact():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = FormatPage(inv)
    assert p.wipeWarningLabel.text() == "This will erase the disk."


def test_disk_list_shows_name_size_model_and_partlabels():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = FormatPage(inv)
    assert p.diskList.count() == 1
    text = p.diskList.item(0).text()
    assert "sdb" in text
    assert "500G" in text
    assert "Backup Drive" in text
    assert "bak1-efi" in text
    assert "sda" not in text.split()[0]


def test_existing_backup_set_does_not_enable():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = FormatPage(inv)
    p.diskList.setCurrentRow(0)
    p.psetEdit.setText("bak1")
    p.confirmEdit.setText("sdb")
    p._sync_enabled()
    assert not p.formatButton.isEnabled()


def test_confirm_path_and_invalid_pset_stay_disabled():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = FormatPage(inv)
    p.diskList.setCurrentRow(0)
    p.psetEdit.setText("bak9")
    p.confirmEdit.setText("/dev/sdb")
    p._sync_enabled()
    assert not p.formatButton.isEnabled()
    p.confirmEdit.setText("sdb")
    p.psetEdit.setText("bak-9")
    p._sync_enabled()
    assert not p.formatButton.isEnabled()
    p.psetEdit.setText("")
    p._sync_enabled()
    assert not p.formatButton.isEnabled()
    p.diskList.clearSelection()
    p.psetEdit.setText("bak9")
    p.confirmEdit.setText("sdb")
    p._sync_enabled()
    assert not p.formatButton.isEnabled()


def test_empty_candidates_message():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    p = FormatPage(inv)
    assert p.diskList.count() == 0
    assert p.emptyDiskLabel.text() == (
        "Plug in a new disk that is not this computer's system disk."
    )
    assert not p.emptyDiskLabel.isHidden()
    p.psetEdit.setText("bak9")
    p.confirmEdit.setText("sda")
    p._sync_enabled()
    assert not p.formatButton.isEnabled()


def test_named_hides_empty_message():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = FormatPage(inv)
    assert p.emptyDiskLabel.isHidden()


def test_two_candidates_listed():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_two_backups.json").read_text())
    p = FormatPage(inv)
    assert p.diskList.count() == 2
    names = [p.diskList.item(i).text().split()[0] for i in range(p.diskList.count())]
    assert names == ["sdb", "sdc"]


def test_prepare_button_shows_format_page():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    assert w.stack.currentIndex() == PAGE_HOME
    assert w.stack.indexOf(w.formatPage) == PAGE_FORMAT
    w.formatButton.click()
    assert w.stack.currentIndex() == PAGE_FORMAT


def test_leave_returns_home_without_helper():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    calls = []
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: calls.append(argv),
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
    )
    w.formatButton.click()
    w.formatPage.leaveButton.click()
    assert w.stack.currentIndex() == PAGE_HOME
    assert calls == []


def _ready_format(w):
    w.formatButton.click()
    w.formatPage.diskList.setCurrentRow(0)
    w.formatPage.psetEdit.setText("bak9")
    w.formatPage.confirmEdit.setText("sdb")
    w.formatPage._sync_enabled()


def test_format_runs_format_disk_not_live():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    captured = []
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: captured.append(argv),
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
    )
    _ready_format(w)
    w.formatPage.formatButton.click()
    assert len(captured) == 1
    assert captured[0] == [
        "pkexec",
        "/usr/lib/mbu-gui/mbu-gui-helper",
        "format-disk",
        "--disk",
        "sdb",
        "--pset",
        "bak9",
    ]


def test_format_success_skip_unplug_and_home():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    captured = []
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: captured.append(argv),
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
        ask_copy_now=lambda: False,
    )
    _ready_format(w)
    w.formatPage.formatButton.click()
    w.on_format_finished(0)
    assert w.stack.currentIndex() == PAGE_HOME
    assert not w.unplugBanner.isHidden()
    assert len(captured) == 1
    assert "format-disk" in captured[0]


def test_format_success_copy_everything_now():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    captured = []
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: captured.append(argv),
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
        ask_copy_now=lambda: True,
    )
    _ready_format(w)
    w.formatPage.formatButton.click()
    w.on_format_finished(0)
    assert len(captured) == 2
    assert captured[1] == [
        "pkexec",
        "/usr/lib/mbu-gui/mbu-gui-helper",
        "backup",
        "--fselection",
        "-bootfix,efi,root,home,swap",
    ]
    w.on_helper_finished(0)
    assert w.stack.currentIndex() == PAGE_HOME
    assert not w.unplugBanner.isHidden()


def test_format_failure_no_unplug():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: None,
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
        ask_copy_now=lambda: True,
    )
    _ready_format(w)
    w.formatPage.formatButton.click()
    w.on_format_finished(1)
    assert failed_command_message(1) in w.logView.toPlainText()
    assert w.unplugBanner.isHidden()
    assert w.stack.currentIndex() == PAGE_HOME


def test_missing_helper_does_not_format():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    calls = []
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=False,
        pkexec_exists=True,
        start_process=lambda argv: calls.append(argv),
        helper_path=None,
    )
    _ready_format(w)
    w.formatPage.formatButton.click()
    assert calls == []
    assert "not installed" in w.logView.toPlainText().lower()
    assert w.unplugBanner.isHidden()
    assert w.stack.currentIndex() == PAGE_HOME
