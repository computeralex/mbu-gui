# tests/test_setup_page.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from mbu_gui.disks import load_lsblk
from mbu_gui.helper_client import failed_command_message
from mbu_gui.main_window import PAGE_BROWSE, PAGE_FORMAT, PAGE_HOME, PAGE_SETUP, MainWindow
from mbu_gui.setup_page import SetupPage

FIXTURES = Path(__file__).parent / "fixtures"
_app = None
def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app

def test_apply_disabled_until_typed_name():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    p = SetupPage(inv)
    assert p.setNameEdit.text() == "main"
    assert not p.applyButton.isEnabled()
    p.confirmEdit.setText("main")
    p._sync_enabled()
    assert p.applyButton.isEnabled()
    p.confirmEdit.setText("maine")
    p._sync_enabled()
    assert not p.applyButton.isEnabled()
    arg = p.labels_arg()
    assert "main-root" in arg
    assert "sdb" not in arg


def test_already_named_offers_leave():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = SetupPage(inv)
    assert "leave them alone" in p.alreadyNamedLabel.text().lower()
    assert p.leaveButton is not None


def test_already_named_exact_copy_and_leave_text():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = SetupPage(inv)
    assert p.alreadyNamedLabel.text() == (
        "Partitions already use MBU names (set main). You can leave them alone."
    )
    assert p.leaveButton.text() == "Leave them alone"


def test_copy_does_not_erase():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    p = SetupPage(inv)
    text = p.safetyLabel.text().lower()
    assert "only names partitions" in text
    assert "does not erase" in text


def test_invalid_set_name_keeps_apply_disabled():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    p = SetupPage(inv)
    p.setNameEdit.setText("main-1")
    p.confirmEdit.setText("main-1")
    p._sync_enabled()
    assert not p.applyButton.isEnabled()


def test_apply_disabled_for_live_set_and_backup_set():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = SetupPage(inv)
    p.setNameEdit.setText("main")
    p.confirmEdit.setText("main")
    p._sync_enabled()
    assert not p.applyButton.isEnabled()
    p.setNameEdit.setText("bak1")
    p.confirmEdit.setText("bak1")
    p._sync_enabled()
    assert not p.applyButton.isEnabled()
    p.setNameEdit.setText("newset")
    p.confirmEdit.setText("newset")
    p._sync_enabled()
    assert p.applyButton.isEnabled()


def test_every_disabled_state_says_why():
    """Apply names was as silent as the format button when blocked."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    p = SetupPage(inv)
    # The default name is "main", which is what this computer already uses, so a
    # freshly opened page on an already-named machine starts with a dead button.
    p.setNameEdit.setText("main")
    p.confirmEdit.setText("main")
    p._sync_enabled()
    assert not p.applyButton.isEnabled()
    assert "already named" in p.blockReasonLabel.text()

    p.setNameEdit.setText("bak1")
    p.confirmEdit.setText("bak1")
    p._sync_enabled()
    assert not p.applyButton.isEnabled()
    assert "already used by a backup disk" in p.blockReasonLabel.text()

    p.setNameEdit.setText("new-set")
    p._sync_enabled()
    assert "letters and digits" in p.blockReasonLabel.text()

    p.setNameEdit.setText("newset")
    p.confirmEdit.setText("")
    p._sync_enabled()
    assert "Type newset" in p.blockReasonLabel.text()

    p.confirmEdit.setText("newset")
    p._sync_enabled()
    assert p.applyButton.isEnabled()
    assert p.blockReasonLabel.text() == ""


def test_both_pages_identify_the_disk_the_same_way():
    """The two flows described their target disk in different terms.

    Prepare listed model and serial with no mount points; Set up listed mount
    points with no disk identity. Both now carry the same identity line.
    """
    app()
    from mbu_gui.format_page import FormatPage

    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    setup = SetupPage(inv)
    fmt = FormatPage(inv)
    fmt.diskList.setCurrentRow(0)
    fmt._sync_enabled()

    # Same shape of line on both: device, size, model, hardware id. The id is
    # whichever the disk reports, so sda shows its WWN and sdb its serial.
    from mbu_gui.disks import find_disk

    live = find_disk(inv, inv.live_disk)
    target = find_disk(inv, "sdb")
    for label, disk in ((setup.diskInfoLabel, live), (fmt.diskInfoLabel, target)):
        assert disk is not None and disk.disk_id is not None
        assert disk.name in label.text()
        assert disk.size in label.text()
        assert disk.disk_id in label.text()

    # Both show per-partition mount points and current labels.
    setup_headers = [
        setup.previewTable.horizontalHeaderItem(i).text()
        for i in range(setup.previewTable.columnCount())
    ]
    fmt_headers = [
        fmt.partitionTable.horizontalHeaderItem(i).text()
        for i in range(fmt.partitionTable.columnCount())
    ]
    assert fmt_headers == ["device", "size", "mount", "current label"]
    assert setup_headers[: len(fmt_headers)] == fmt_headers


def test_preview_live_partitions_only():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    p = SetupPage(inv)
    headers = [
        p.previewTable.horizontalHeaderItem(i).text()
        for i in range(p.previewTable.columnCount())
    ]
    assert headers == ["device", "size", "mount", "current label", "proposed label"]
    devices = [p.previewTable.item(row, 0).text() for row in range(p.previewTable.rowCount())]
    assert devices == ["sda1", "sda2", "sda3", "sda4"]
    proposed = [p.previewTable.item(row, 4).text() for row in range(p.previewTable.rowCount())]
    assert "main-root" in proposed
    assert "main-efi" in proposed
    assert p.labels_arg() == "sda1=main-efi,sda2=main-root,sda3=main-home,sda4=main-swap"


def test_setup_button_shows_setup_page():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    assert w.stack.currentIndex() == PAGE_HOME
    assert w.stack.indexOf(w.homePage) == PAGE_HOME
    assert w.stack.indexOf(w.setupPage) == PAGE_SETUP
    assert w.stack.indexOf(w.formatPage) == PAGE_FORMAT
    assert w.stack.indexOf(w.browsePage) == PAGE_BROWSE
    w.setupButton.click()
    assert w.stack.currentIndex() == PAGE_SETUP


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
    w.setupButton.click()
    w.setupPage.leaveButton.click()
    assert w.stack.currentIndex() == PAGE_HOME
    assert calls == []


def test_apply_runs_label_live_not_format():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    captured = []
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: captured.append(argv),
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
    )
    w.setupButton.click()
    w.setupPage.confirmEdit.setText("main")
    w.setupPage._sync_enabled()
    w.setupPage.applyButton.click()
    assert len(captured) == 1
    argv = captured[0]
    assert argv[0] == "pkexec"
    assert argv[1:] == [
        "/usr/lib/mbu-gui/mbu-gui-helper",
        "label-live",
        "--labels",
        "sda1=main-efi,sda2=main-root,sda3=main-home,sda4=main-swap",
    ]
    assert "format-disk" not in argv
    assert "sdb" not in argv[-1]


def test_apply_success_reloads_and_returns_home():
    app()
    unnamed = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    named = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(
        inventory=unnamed,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: None,
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
        reload_inventory=lambda: named,
    )
    w.setupButton.click()
    w.setupPage.confirmEdit.setText("main")
    w.setupPage._sync_enabled()
    w.setupPage.applyButton.click()
    w.on_label_live_finished(0)
    assert w.stack.currentIndex() == PAGE_HOME
    assert w.inventory.live_set == "main"
    assert w.inventory.unnamed_live is False
    assert w.startButton.isEnabled()
    assert w.unplugBanner.isHidden()


def test_apply_failure_stays_visible_without_unplug():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: None,
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
    )
    w.setupButton.click()
    w.setupPage.confirmEdit.setText("main")
    w.setupPage._sync_enabled()
    w.setupPage.applyButton.click()
    w.on_label_live_finished(1)
    assert w.stack.currentIndex() == PAGE_HOME
    assert failed_command_message(1, "label") in w.logView.toPlainText()
    assert w.unplugBanner.isHidden()
    assert w.inventory.unnamed_live is True
