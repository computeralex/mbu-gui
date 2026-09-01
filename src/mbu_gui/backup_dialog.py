from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from mbu_gui.disks import Inventory, describe_backup_route

BOOT_FIX_WARN = (
    "Without boot fix, the backup disk might not boot if you copy root, boot, or efi."
)
UNKNOWN_DESTINATION_TEXT = (
    "Cannot tell which disk would be overwritten, so this backup will not start. "
    "Go back, make sure exactly one backup disk is plugged in, and try again."
)


class BackupDialog(QDialog):
    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.setWindowTitle("Start Backup")
        self._function_checks: list[tuple[str, QCheckBox]] = []

        layout = QVBoxLayout(self)

        self.route = describe_backup_route(inventory)
        self.destinationLabel = QLabel(
            self.route if self.route is not None else UNKNOWN_DESTINATION_TEXT
        )
        self.destinationLabel.setObjectName("destinationLabel")
        self.destinationLabel.setWordWrap(True)
        destination_font = QFont(self.destinationLabel.font())
        destination_font.setBold(True)
        self.destinationLabel.setFont(destination_font)
        layout.addWidget(self.destinationLabel)

        self.bootFixCheck = QCheckBox("Boot fix")
        self.bootFixCheck.setObjectName("bootFixCheck")
        self.bootFixCheck.setChecked(True)
        layout.addWidget(self.bootFixCheck)

        self.bootFixWarnLabel = QLabel(BOOT_FIX_WARN)
        self.bootFixWarnLabel.setObjectName("bootFixWarnLabel")
        self.bootFixWarnLabel.setWordWrap(True)
        self.bootFixWarnLabel.setVisible(False)
        layout.addWidget(self.bootFixWarnLabel)
        self.bootFixCheck.toggled.connect(self._on_boot_fix_toggled)

        for function in inventory.live_functions:
            box = QCheckBox(function)
            box.setObjectName(f"functionCheck_{function}")
            box.setChecked(True)
            self._function_checks.append((function, box))
            layout.addWidget(box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.okButton = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.okButton.setObjectName("okButton")
        self.okButton.setEnabled(self.route is not None)

    def _on_boot_fix_toggled(self, checked: bool) -> None:
        self.bootFixWarnLabel.setVisible(not checked)

    def fselection(self) -> str:
        parts: list[str] = []
        if self.bootFixCheck.isChecked():
            parts.append("-bootfix")
        for function, box in self._function_checks:
            if box.isChecked():
                parts.append(function)
        return ",".join(parts)
