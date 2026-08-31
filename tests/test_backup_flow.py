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


def test_failure_stays_on_screen():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, helper_exists=True, pkexec_exists=True, start_process=lambda argv: None, helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"))
    w.on_helper_finished(1)
    assert failed_command_message(1) in w.logView.toPlainText()
    assert w.unplugBanner.isHidden()


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
