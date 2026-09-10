from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mbu_gui.disks import Inventory, describe_backup_route
from mbu_gui.wizard import INTRO_TEXT, INTRO_TITLE, resume_note

FINISH_TITLE = "Everything is ready"
FINISH_TEXT = (
    "This computer is named and the backup disk is prepared. The first backup "
    "copies everything across and is the slowest one; later backups only copy "
    "what changed."
)
BACKUP_NOW_TEXT = "Back up now"
FINISH_LATER_TEXT = "Finish without backing up"
FINISH_LATER_NOTE = (
    "Nothing is backed up until a backup runs. You can start one any time from "
    "the main screen."
)


def _title(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont(label.font())
    font.setPointSize(font.pointSize() + 4)
    font.setBold(True)
    label.setFont(font)
    label.setWordWrap(True)
    return label


class WizardIntroPage(QWidget):
    """What this thing is, before anyone is asked to erase a disk."""

    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        layout.addWidget(_title(INTRO_TITLE))

        self.introLabel = QLabel(INTRO_TEXT)
        self.introLabel.setObjectName("introLabel")
        self.introLabel.setWordWrap(True)
        layout.addWidget(self.introLabel)

        note = resume_note(inventory)
        self.resumeLabel = QLabel(note)
        self.resumeLabel.setObjectName("resumeLabel")
        self.resumeLabel.setWordWrap(True)
        self.resumeLabel.setStyleSheet(
            "background-color: #EAF2F8; color: #000000; padding: 8px;"
        )
        self.resumeLabel.setVisible(bool(note))
        layout.addWidget(self.resumeLabel)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        self.startButton = QPushButton("Start")
        self.startButton.setObjectName("wizardStartButton")
        self.leaveButton = QPushButton("Not now")
        self.leaveButton.setObjectName("wizardLeaveButton")
        buttons.addWidget(self.startButton)
        buttons.addWidget(self.leaveButton)
        layout.addLayout(buttons)

    def update_for(self, inventory: Inventory) -> None:
        note = resume_note(inventory)
        self.resumeLabel.setText(note)
        self.resumeLabel.setVisible(bool(note))


class WizardFinishPage(QWidget):
    """The last step: run the backup, or stop here having set everything up."""

    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.stepLabel = QLabel("")
        self.stepLabel.setObjectName("stepLabel")
        layout.addWidget(self.stepLabel)

        layout.addWidget(_title(FINISH_TITLE))

        self.detailLabel = QLabel(FINISH_TEXT)
        self.detailLabel.setObjectName("detailLabel")
        self.detailLabel.setWordWrap(True)
        layout.addWidget(self.detailLabel)

        # Same route description the confirmation dialog uses, so the last
        # screen before a write names the disk that is about to be written to.
        route = describe_backup_route(inventory)
        self.routeLabel = QLabel(route or "")
        self.routeLabel.setObjectName("routeLabel")
        self.routeLabel.setWordWrap(True)
        self.routeLabel.setVisible(bool(route))
        layout.addWidget(self.routeLabel)

        self.laterNoteLabel = QLabel(FINISH_LATER_NOTE)
        self.laterNoteLabel.setObjectName("laterNoteLabel")
        self.laterNoteLabel.setWordWrap(True)
        layout.addWidget(self.laterNoteLabel)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        self.backupButton = QPushButton(BACKUP_NOW_TEXT)
        self.backupButton.setObjectName("wizardBackupButton")
        self.laterButton = QPushButton(FINISH_LATER_TEXT)
        self.laterButton.setObjectName("wizardLaterButton")
        buttons.addWidget(self.backupButton)
        buttons.addWidget(self.laterButton)
        layout.addLayout(buttons)

    def set_step(self, text: str) -> None:
        self.stepLabel.setText(text)
        self.stepLabel.setVisible(bool(text))

    def update_for(self, inventory: Inventory) -> None:
        route = describe_backup_route(inventory)
        self.routeLabel.setText(route or "")
        self.routeLabel.setVisible(bool(route))
        # Without a known destination there is nothing safe to start.
        self.backupButton.setEnabled(route is not None)
