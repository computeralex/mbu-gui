from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from mbu_gui.version import __version__, read_mbu_release

ABOUT_BODY = (
    "MBU GUI is a window for Ted Merrill's MBU bootable-backup scripts.\n"
    "It is a wrapper, not a rewrite, and does not speak for Ted."
)


class AboutDialog(QDialog):
    def __init__(self, *, mbu_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About MBU Backup")
        layout = QVBoxLayout(self)

        self.guiVersionLabel = QLabel(f"MBU GUI: {__version__}")
        self.guiVersionLabel.setObjectName("guiVersionLabel")
        layout.addWidget(self.guiVersionLabel)

        mbu_release = read_mbu_release(mbu_dir)
        self.mbuVersionLabel = QLabel(f"MBU: {mbu_release}")
        self.mbuVersionLabel.setObjectName("mbuVersionLabel")
        layout.addWidget(self.mbuVersionLabel)

        body = QLabel(ABOUT_BODY)
        body.setObjectName("aboutBodyLabel")
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
