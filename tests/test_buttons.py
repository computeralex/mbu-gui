import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget

from mbu_gui.buttons import add_leave_proceed_row
from mbu_gui.disks import load_lsblk
from mbu_gui.format_page import FormatPage
from mbu_gui.setup_page import SetupPage
from mbu_gui.wizard_page import WizardFinishPage, WizardIntroPage

FIXTURES = Path(__file__).parent / "fixtures"
_app = None


def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app


def _left_then_right(row: QHBoxLayout) -> tuple[str, str]:
    # leave, stretch, proceed → widgets at 0 and 2
    left = row.itemAt(0).widget()
    right = row.itemAt(row.count() - 1).widget()
    assert isinstance(left, QPushButton)
    assert isinstance(right, QPushButton)
    return left.text(), right.text()


def test_add_leave_proceed_row_orders_left_to_right():
    app()
    host = QWidget()
    row = QHBoxLayout(host)
    leave = QPushButton("Cancel")
    proceed = QPushButton("Continue")
    add_leave_proceed_row(row, leave, proceed)
    assert _left_then_right(row) == ("Cancel", "Continue")


def test_wizard_intro_puts_leave_left_of_proceed():
    app()
    page = WizardIntroPage(load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text()))
    row = page.layout().itemAt(page.layout().count() - 1).layout()
    assert _left_then_right(row) == ("Not now", "Start")


def test_wizard_finish_puts_later_left_of_backup():
    app()
    page = WizardFinishPage(load_lsblk((FIXTURES / "lsblk_named.json").read_text()))
    row = page.layout().itemAt(page.layout().count() - 1).layout()
    assert _left_then_right(row) == ("Finish without backing up", "Back up now")


def test_setup_puts_leave_left_of_apply():
    app()
    page = SetupPage(load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text()))
    row = page.layout().itemAt(page.layout().count() - 1).layout()
    assert _left_then_right(row)[0] == "Cancel"
    assert _left_then_right(row)[1] == "Apply names"


def test_format_puts_leave_left_of_format():
    app()
    page = FormatPage(load_lsblk((FIXTURES / "lsblk_named.json").read_text()))
    row = page.layout().itemAt(page.layout().count() - 1).layout()
    assert _left_then_right(row) == ("Cancel", "Format disk")
