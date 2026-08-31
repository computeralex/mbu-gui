from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mbu_gui.disks import Inventory
from mbu_gui.logs import LastRun, current_file_from_line, last_run_label

UNPLUG_BANNER_TEXT = (
    "Unplug the backup disk now.\n"
    "Duplicate UUIDs confuse Linux if you leave it plugged in."
)


def _icon_path() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    for candidate in (
        root / "vendor" / "mbu" / "mbu-icon.png",
        root / "data" / "mbu-icon.png",
    ):
        if candidate.exists():
            return candidate
    return None


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        inventory: Inventory,
        last_run: LastRun | None,
        helper_exists: bool = True,
        pkexec_exists: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.inventory = inventory
        self.last_run = last_run
        self.helper_exists = helper_exists
        self.pkexec_exists = pkexec_exists
        self._running = False

        self.setWindowTitle("MBU Backup")
        icon = _icon_path()
        if icon is not None:
            self.setWindowIcon(QIcon(str(icon)))

        central = QWidget(self)
        layout = QVBoxLayout(central)

        title = QLabel("MBU Backup")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self.statusLabel = QLabel(inventory.status_line)
        self.statusLabel.setObjectName("statusLabel")
        layout.addWidget(self.statusLabel)

        self.lastRunLabel = QLabel(last_run_label(last_run))
        self.lastRunLabel.setObjectName("lastRunLabel")
        layout.addWidget(self.lastRunLabel)

        self.startButton = QPushButton("Start Backup")
        self.startButton.setObjectName("startButton")
        start_font = QFont(self.startButton.font())
        start_font.setPointSize(start_font.pointSize() + 4)
        start_font.setBold(True)
        self.startButton.setFont(start_font)
        self.startButton.setMinimumHeight(48)
        self.startButton.setEnabled(inventory.start_blocked_reason is None)
        layout.addWidget(self.startButton)

        self.startReasonLabel = QLabel(inventory.start_blocked_reason or "")
        self.startReasonLabel.setObjectName("startReasonLabel")
        self.startReasonLabel.setWordWrap(True)
        layout.addWidget(self.startReasonLabel)

        secondary = QHBoxLayout()
        self.setupButton = QPushButton("Set up this computer")
        self.setupButton.setObjectName("setupButton")
        self.formatButton = QPushButton("Prepare a backup disk")
        self.formatButton.setObjectName("formatButton")
        self.browseButton = QPushButton("Browse a backup")
        self.browseButton.setObjectName("browseButton")
        secondary.addWidget(self.setupButton)
        secondary.addWidget(self.formatButton)
        secondary.addWidget(self.browseButton)
        layout.addLayout(secondary)

        self.currentFileLabel = QLabel("")
        self.currentFileLabel.setObjectName("currentFileLabel")
        layout.addWidget(self.currentFileLabel)

        self.logView = QPlainTextEdit()
        self.logView.setObjectName("logView")
        self.logView.setReadOnly(True)
        self.logView.setMinimumHeight(160)
        layout.addWidget(self.logView)

        self.unplugBanner = QLabel(UNPLUG_BANNER_TEXT)
        self.unplugBanner.setObjectName("unplugBanner")
        self.unplugBanner.setWordWrap(True)
        banner_font = QFont(self.unplugBanner.font())
        banner_font.setBold(True)
        self.unplugBanner.setFont(banner_font)
        self.unplugBanner.setStyleSheet(
            "background-color: #F4D03F; color: #000000; font-weight: bold; padding: 12px;"
        )
        self.unplugBanner.hide()
        layout.addWidget(self.unplugBanner)

        self.setCentralWidget(central)
        self.resize(720, 560)

    def show_unplug(self, visible: bool) -> None:
        self.unplugBanner.setVisible(visible)

    def append_log(self, line: str) -> None:
        self.logView.appendPlainText(line)
        current = current_file_from_line(line)
        if current is not None:
            self.currentFileLabel.setText(current)

    def show_error(self, message: str) -> None:
        self.append_log(message)
        if not self._running:
            self.startButton.setEnabled(self.inventory.start_blocked_reason is None)

    def set_running(self, running: bool) -> None:
        self._running = running
        idle = not running
        self.setupButton.setEnabled(idle)
        self.formatButton.setEnabled(idle)
        self.browseButton.setEnabled(idle)
        if running:
            self.startButton.setEnabled(False)
        else:
            self.startButton.setEnabled(self.inventory.start_blocked_reason is None)
