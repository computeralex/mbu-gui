from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mbu_gui.disks import Disk, Inventory, candidate_backup_disks, is_valid_set_name

WIPE_WARNING = "This will erase the disk."
EMPTY_DISK_TEXT = "Plug in a new disk that is not this computer's system disk."


def _disk_item_text(disk: Disk) -> str:
    labels = ", ".join(part.partlabel for part in disk.partitions if part.partlabel)
    model = disk.model or ""
    return "  ".join(part for part in (disk.name, disk.size, model, labels) if part)


class FormatPage(QWidget):
    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        self.inventory = inventory

        layout = QVBoxLayout(self)

        title = QLabel("Prepare a backup disk")
        layout.addWidget(title)

        self.wipeWarningLabel = QLabel(WIPE_WARNING)
        self.wipeWarningLabel.setObjectName("wipeWarningLabel")
        self.wipeWarningLabel.setWordWrap(True)
        layout.addWidget(self.wipeWarningLabel)

        self.emptyDiskLabel = QLabel(EMPTY_DISK_TEXT)
        self.emptyDiskLabel.setObjectName("emptyDiskLabel")
        self.emptyDiskLabel.setWordWrap(True)
        layout.addWidget(self.emptyDiskLabel)

        self.diskList = QListWidget()
        self.diskList.setObjectName("diskList")
        self.diskList.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.diskList)

        layout.addWidget(QLabel("New set name"))
        self.psetEdit = QLineEdit()
        self.psetEdit.setObjectName("psetEdit")
        self.psetEdit.setPlaceholderText("Letters and digits only")
        layout.addWidget(self.psetEdit)

        layout.addWidget(QLabel("Type the disk name to confirm"))
        self.confirmEdit = QLineEdit()
        self.confirmEdit.setObjectName("confirmEdit")
        self.confirmEdit.setPlaceholderText("Type the disk name, for example sdb")
        layout.addWidget(self.confirmEdit)

        buttons = QHBoxLayout()
        self.formatButton = QPushButton("Format disk")
        self.formatButton.setObjectName("formatButton")
        self.leaveButton = QPushButton("Cancel")
        self.leaveButton.setObjectName("leaveButton")
        buttons.addWidget(self.formatButton)
        buttons.addWidget(self.leaveButton)
        layout.addLayout(buttons)

        self.diskList.itemSelectionChanged.connect(self._sync_enabled)
        self.diskList.currentItemChanged.connect(self._sync_enabled)
        self.psetEdit.textChanged.connect(self._sync_enabled)
        self.confirmEdit.textChanged.connect(self._sync_enabled)
        self._fill_disks()
        self._sync_enabled()

    def _fill_disks(self) -> None:
        disks = candidate_backup_disks(self.inventory)
        self.diskList.clear()
        for disk in disks:
            item = QListWidgetItem(_disk_item_text(disk))
            item.setData(Qt.ItemDataRole.UserRole, disk.name)
            self.diskList.addItem(item)
        empty = not disks
        self.emptyDiskLabel.setVisible(empty)
        self.diskList.setVisible(not empty)

    def selected_disk_name(self) -> str | None:
        items = self.diskList.selectedItems()
        if len(items) != 1:
            return None
        name = items[0].data(Qt.ItemDataRole.UserRole)
        return name if isinstance(name, str) else None

    def _can_format(self) -> bool:
        name = self.selected_disk_name()
        if name is None:
            return False
        pset = self.psetEdit.text()
        if not is_valid_set_name(pset):
            return False
        if pset == self.inventory.live_set:
            return False
        if pset in self.inventory.backup_sets:
            return False
        return self.confirmEdit.text() == name

    def _sync_enabled(self, *args) -> None:
        self.formatButton.setEnabled(self._can_format())
