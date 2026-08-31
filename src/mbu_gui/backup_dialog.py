from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from mbu_gui.disks import Inventory

BOOT_FIX_WARN = (
    "Without boot fix, the backup disk might not boot if you copy root, boot, or efi."
)


class BackupDialog(QDialog):
    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.setWindowTitle("Start Backup")
        self._function_checks: list[tuple[str, QCheckBox]] = []

        layout = QVBoxLayout(self)

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
