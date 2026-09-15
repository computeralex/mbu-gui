from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from mbu_gui.backup_prefs import load_backup_selection, save_backup_selection
from mbu_gui.disks import Inventory, describe_backup_route

BOOT_FIX_WARN = (
    "Without boot fix, the backup disk might not boot if you copy root, boot, or efi."
)
UNKNOWN_DESTINATION_TEXT = (
    "Cannot tell which disk would be overwritten, so this backup will not start. "
    "Go back, make sure exactly one backup disk is plugged in, and try again."
)


class BackupDialog(QDialog):
    def __init__(
        self,
        inventory: Inventory,
        parent=None,
        *,
        config_dir: Path | None = None,
    ):
        super().__init__(parent)
        self.inventory = inventory
        self._config_dir = config_dir
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
            box.toggled.connect(self._sync_ok)
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
        self._apply_saved_selection()
        self._sync_ok()

    def _apply_saved_selection(self) -> None:
        set_name = self.inventory.live_set
        if not set_name:
            return
        saved = load_backup_selection(set_name, config_dir=self._config_dir)
        if saved is None:
            return
        wanted = set(saved["functions"])
        for function, box in self._function_checks:
            box.setChecked(function in wanted)
        self.bootFixCheck.setChecked(bool(saved["boot_fix"]))

    def _checked_functions(self) -> list[str]:
        return [name for name, box in self._function_checks if box.isChecked()]

    def _sync_ok(self, *_args) -> None:
        has_route = self.route is not None
        has_selection = bool(self._checked_functions())
        self.okButton.setEnabled(has_route and has_selection)

    def _on_boot_fix_toggled(self, checked: bool) -> None:
        self.bootFixWarnLabel.setVisible(not checked)

    def accept(self) -> None:
        set_name = self.inventory.live_set
        if set_name:
            save_backup_selection(
                set_name,
                functions=self._checked_functions(),
                boot_fix=self.bootFixCheck.isChecked(),
                config_dir=self._config_dir,
            )
        super().accept()

    def fselection(self) -> str:
        parts: list[str] = []
        if self.bootFixCheck.isChecked():
            parts.append("-bootfix")
        parts.extend(self._checked_functions())
        return ",".join(parts)
