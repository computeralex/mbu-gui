import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtWidgets import QApplication

from mbu_gui.disks import load_lsblk
from mbu_gui.wizard_page import (
    WIZARD_CANCEL_TEXT,
    WIZARD_CONTINUE_TEXT,
    WIZARD_LEAVE_TEXT,
    WIZARD_START_TEXT,
    WizardIntroPage,
)

FIXTURES = Path(__file__).parent / "fixtures"
_app = None


def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app


def test_first_time_intro_uses_start_and_not_now():
    app()
    page = WizardIntroPage(load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text()))
    assert page.startButton.text() == WIZARD_START_TEXT
    assert page.leaveButton.text() == WIZARD_LEAVE_TEXT
    assert page.resumeLabel.text() == ""


def test_resume_intro_uses_continue_and_cancel():
    app()
    page = WizardIntroPage(load_lsblk((FIXTURES / "lsblk_named.json").read_text()))
    assert page.startButton.text() == WIZARD_CONTINUE_TEXT
    assert page.leaveButton.text() == WIZARD_CANCEL_TEXT
    assert "Next:" in page.resumeLabel.text()
    assert "this computer" not in page.resumeLabel.text().lower()
