# tests/test_backup_flow.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from mbu_gui.backup_dialog import BackupDialog
from mbu_gui.disks import load_lsblk
from mbu_gui.helper_client import failed_command_message
from mbu_gui.main_window import MainWindow

FIXTURES = Path(__file__).parent / "fixtures"
_app = None
def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app

def test_fselection_default():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    d = BackupDialog(inv)
    assert d.bootFixCheck.isChecked()
    fs = d.fselection()
    assert fs.startswith("-bootfix,")
    assert "root" in fs


def test_dialog_names_the_destination_disk():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    d = BackupDialog(inv)
    text = d.destinationLabel.text()
    assert "main" in text  # source set
    assert "bak1" in text  # destination set
    assert "sdb" in text  # destination disk
    assert "500G" in text
    assert "Backup Drive" in text
    assert "serial:usb1111backupb" in text
    assert "sda" not in text  # never points at the live disk
    assert d.okButton.isEnabled()


def test_dialog_refuses_when_destination_is_ambiguous():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_two_backups.json").read_text())
    d = BackupDialog(inv)
    assert d.route is None
    assert not d.okButton.isEnabled()
    assert "Cannot tell which disk" in d.destinationLabel.text()


def test_accepted_dialog_without_route_does_not_start_backup(monkeypatch):
    """Last-ditch guard: even an accepted dialog cannot start an unnamed backup."""
    app()
    from dataclasses import replace
    from PySide6.QtWidgets import QDialog

    import mbu_gui.main_window as main_window

    named = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    # Start is unblocked but no destination can be described.
    inv = replace(named, backup_sets=[], start_blocked_reason=None)
    calls = []
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: calls.append(argv),
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
    )
    monkeypatch.setattr(
        main_window.BackupDialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    # Clicking cannot reach this state any more: with no backup set the primary
    # button offers Prepare a backup disk instead. Drive the backup action
    # directly so the last-ditch guard inside on_start_clicked stays covered.
    from mbu_gui.disks import NextStep

    w._next_step = NextStep("backup", "Back up now", "")
    w.on_start_clicked()
    assert calls == []
    assert "Cannot tell which disk" in w.logView.toPlainText()


def test_success_shows_unplug():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    captured = {}
    def start_process(argv):
        captured["argv"] = argv
    w = MainWindow(inventory=inv, last_run=None, helper_exists=True, pkexec_exists=True, start_process=start_process, helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"))
    w._run_backup_with_fselection("-bootfix,root")  # method called by dialog accept
    assert captured["argv"][0] == "pkexec"
    assert "backup" in captured["argv"]
    w.on_helper_finished(0)
    assert not w.unplugBanner.isHidden()


def test_success_reloads_last_run_label():
    app()
    from mbu_gui.logs import LastRun

    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    last = LastRun(
        timestamp="2026/01/02-03:04:05",
        from_set="main",
        to_set="bak1",
        functions="root,home",
        ok=True,
    )
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: None,
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
        reload_inventory=lambda: inv,
        reload_last_run=lambda: last,
    )
    w._run_backup_with_fselection("root")
    w.on_helper_finished(0)
    assert w.lastRunLabel.text() == "Last backup: 2026/01/02-03:04:05  main → bak1"


def test_failed_backup_still_warns_to_unplug():
    """UUIDs are cloned per partition, so a failed run may already have cloned some."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, helper_exists=True, pkexec_exists=True, start_process=lambda argv: None, helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"))
    w.on_helper_finished(1)
    assert failed_command_message(1) in w.logView.toPlainText()
    assert not w.unplugBanner.isHidden()
    assert "did not finish" in w.unplugBanner.text()
    assert "Unplug the backup disk anyway" in w.unplugBanner.text()


def test_crashed_backup_warns_on_next_launch():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, backup_unfinished=True)
    assert not w.unplugBanner.isHidden()
    assert "did not finish" in w.unplugBanner.text()


def test_unfinished_warning_survives_a_later_failed_format():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, backup_unfinished=True)
    w.on_format_finished(1)
    assert not w.unplugBanner.isHidden()
    assert "did not finish" in w.unplugBanner.text()


def test_unfinished_warning_clears_after_a_good_backup():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, backup_unfinished=True)
    w.on_helper_finished(0)
    w.on_format_finished(1)
    assert w.unplugBanner.isHidden()


def test_clean_launch_shows_no_banner():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, backup_unfinished=False)
    assert w.unplugBanner.isHidden()


def test_successful_backup_uses_the_plain_unplug_text():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, helper_exists=True, pkexec_exists=True, start_process=lambda argv: None, helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"))
    w.on_helper_finished(1)
    assert "did not finish" in w.unplugBanner.text()
    w.on_helper_finished(0)
    assert not w.unplugBanner.isHidden()
    assert "did not finish" not in w.unplugBanner.text()
    assert "Unplug the backup disk now" in w.unplugBanner.text()


def test_cancelled_pkexec_message():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, helper_exists=True, pkexec_exists=True, start_process=lambda argv: None, helper_path=Path("/x"))
    w.on_helper_finished(126, stderr="Request dismissed")
    assert "cancelled" in w.logView.toPlainText().lower()


def test_missing_helper_message():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, helper_exists=False, pkexec_exists=True, start_process=lambda argv: None, helper_path=None)
    w._run_backup_with_fselection("root")
    assert "not installed" in w.logView.toPlainText().lower()


def test_fselection_order_and_bootfix_warn():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    d = BackupDialog(inv)
    assert d.fselection() == "-bootfix,efi,root,home,swap"
    assert d.bootFixWarnLabel.isHidden()
    d.bootFixCheck.setChecked(False)
    assert not d.bootFixWarnLabel.isHidden()
    assert d.bootFixWarnLabel.text() == (
        "Without boot fix, the backup disk might not boot if you copy root, boot, or efi."
    )
    assert d.fselection() == "efi,root,home,swap"


def test_does_not_start_two_helpers():
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
    w._run_backup_with_fselection("root")
    w._run_backup_with_fselection("home")
    assert len(calls) == 1
    assert calls[0] == [
        "pkexec",
        "/usr/lib/mbu-gui/mbu-gui-helper",
        "backup",
        "--fselection",
        "root",
    ]


def test_blocked_start_does_not_open_dialog():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    calls = []
    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: calls.append(argv),
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
    )
    w.on_start_clicked()
    assert calls == []


def test_line_process_emits_lines_and_exit_code():
    app()
    from PySide6.QtCore import QEventLoop, QTimer
    from mbu_gui.process import LineProcess

    proc = LineProcess()
    lines: list[str] = []
    codes: list[int] = []
    proc.line.connect(lines.append)
    proc.finished.connect(codes.append)
    loop = QEventLoop()
    proc.finished.connect(loop.quit)
    proc.start(["python3", "-c", "print('one'); print('two')"])
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert lines == ["one", "two"]
    assert codes == [0]


def test_line_process_flushes_partial_line():
    app()
    from PySide6.QtCore import QEventLoop, QTimer
    from mbu_gui.process import LineProcess

    proc = LineProcess()
    lines: list[str] = []
    proc.line.connect(lines.append)
    loop = QEventLoop()
    proc.finished.connect(loop.quit)
    proc.start(["python3", "-c", "import sys; sys.stdout.write('partial')"])
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert lines == ["partial"]
