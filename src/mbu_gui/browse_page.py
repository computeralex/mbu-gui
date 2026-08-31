from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import subprocess

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mbu_gui.disks import Inventory
from mbu_gui.paths import resolve_paths

NO_BACKUP_TEXT = "Plug in the backup disk"
UNMOUNT_FAIL_TEXT = (
    "Could not unmount. Close the file manager, click away from those folders, then try Unmount again."
)


def _xdg_open(path: str) -> None:
    subprocess.Popen(["xdg-open", path])


class BrowsePage(QWidget):
    def __init__(
        self,
        inventory: Inventory,
        parent=None,
        *,
        open_dir: Callable[[str], None] | None = None,
        mount_dir: Path | None = None,
    ):
        super().__init__(parent)
        self.inventory = inventory
        self.open_dir = open_dir
        self.mount_dir = mount_dir if mount_dir is not None else resolve_paths().mount_dir
        self.mounted = False

        layout = QVBoxLayout(self)

        title = QLabel("Browse a backup")
        layout.addWidget(title)

        self.busyLabel = QLabel("")
        self.busyLabel.setObjectName("busyLabel")
        self.busyLabel.setWordWrap(True)
        layout.addWidget(self.busyLabel)

        self.setList = QListWidget()
        self.setList.setObjectName("setList")
        self.setList.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.setList)

        buttons = QHBoxLayout()
        self.mountButton = QPushButton("Mount")
        self.mountButton.setObjectName("mountButton")
        self.openButton = QPushButton("Open")
        self.openButton.setObjectName("openButton")
        self.unmountButton = QPushButton("Unmount")
        self.unmountButton.setObjectName("unmountButton")
        self.leaveButton = QPushButton("Cancel")
        self.leaveButton.setObjectName("leaveButton")
        buttons.addWidget(self.mountButton)
        buttons.addWidget(self.openButton)
        buttons.addWidget(self.unmountButton)
        buttons.addWidget(self.leaveButton)
        layout.addLayout(buttons)

        self.setList.itemSelectionChanged.connect(self._sync_enabled)
        self.setList.currentItemChanged.connect(self._sync_enabled)
        self._fill_sets()
        self._sync_enabled()

    def _fill_sets(self) -> None:
        self.setList.clear()
        for name in self.inventory.backup_sets:
            self.setList.addItem(QListWidgetItem(name))
        if self.setList.count() == 1:
            self.setList.setCurrentRow(0)
        if not self.inventory.backup_sets:
            self.busyLabel.setText(NO_BACKUP_TEXT)
        else:
            self.busyLabel.setText("")

    def selected_set_name(self) -> str | None:
        items = self.setList.selectedItems()
        if len(items) != 1:
            return None
        return items[0].text()

    def _can_mount(self) -> bool:
        return (not self.mounted) and self.selected_set_name() is not None

    def _sync_enabled(self, *args) -> None:
        self.mountButton.setEnabled(self._can_mount())
        self.openButton.setEnabled(self.mounted)
        self.unmountButton.setEnabled(self.mounted)
        self.leaveButton.setEnabled(not self.mounted)

    def set_mounted(self, mounted: bool) -> None:
        self.mounted = mounted
        self._sync_enabled()

    def open_mount_dir(self) -> None:
        opener = self.open_dir if self.open_dir is not None else _xdg_open
        opener(str(self.mount_dir))
