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

from mbu_gui.disks import (
    Disk,
    Inventory,
    candidate_backup_disks,
    confirm_token,
    is_valid_set_name,
)

WIPE_WARNING = "This will erase the disk."
EMPTY_DISK_TEXT = "Plug in a new disk that is not this computer's system disk."
NO_DISK_ID_TEXT = (
    "This disk reports no serial number, so MBU cannot tell it apart from "
    "another disk after a replug. Refusing to format it."
)
CONFIRM_PROMPT = "Type the confirmation code for the disk you selected"
_DISK_ID_ROLE = Qt.ItemDataRole.UserRole + 1


def _disk_item_text(disk: Disk) -> str:
    labels = ", ".join(part.partlabel for part in disk.partitions if part.partlabel)
    serial = f"serial {disk.serial}" if disk.serial else ""
    model = disk.model or ""
    return "  ".join(
        part for part in (disk.name, disk.size, model, serial, labels) if part
    )


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

        self.confirmPromptLabel = QLabel(CONFIRM_PROMPT)
        self.confirmPromptLabel.setObjectName("confirmPromptLabel")
        self.confirmPromptLabel.setWordWrap(True)
        layout.addWidget(self.confirmPromptLabel)

        self.confirmEdit = QLineEdit()
        self.confirmEdit.setObjectName("confirmEdit")
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
            item.setData(_DISK_ID_ROLE, disk.disk_id)
            self.diskList.addItem(item)
        empty = not disks
        self.emptyDiskLabel.setVisible(empty)
        self.diskList.setVisible(not empty)

    def _selected_disk(self) -> Disk | None:
        items = self.diskList.selectedItems()
        if len(items) != 1:
            return None
        name = items[0].data(Qt.ItemDataRole.UserRole)
        for disk in candidate_backup_disks(self.inventory):
            if disk.name == name:
                return disk
        return None

    def selected_disk_name(self) -> str | None:
        disk = self._selected_disk()
        return None if disk is None else disk.name

    def selected_disk_id(self) -> str | None:
        disk = self._selected_disk()
        return None if disk is None else disk.disk_id

    def _can_format(self) -> bool:
        disk = self._selected_disk()
        if disk is None or disk.disk_id is None:
            return False
        pset = self.psetEdit.text()
        if not is_valid_set_name(pset):
            return False
        if pset == self.inventory.live_set:
            return False
        if pset in self.inventory.backup_sets:
            return False
        return self.confirmEdit.text().strip().lower() == confirm_token(disk)

    def _sync_prompt(self) -> None:
        disk = self._selected_disk()
        if disk is None:
            self.confirmPromptLabel.setText(CONFIRM_PROMPT)
            self.confirmEdit.setPlaceholderText("")
            return
        if disk.disk_id is None:
            self.confirmPromptLabel.setText(NO_DISK_ID_TEXT)
            self.confirmEdit.setPlaceholderText("")
            return
        token = confirm_token(disk)
        self.confirmPromptLabel.setText(
            f"To erase {disk.size} {disk.model or disk.name} "
            f"({disk.disk_id}), type this code: {token}"
        )
        self.confirmEdit.setPlaceholderText(token or "")

    def _sync_enabled(self, *args) -> None:
        self._sync_prompt()
        self.formatButton.setEnabled(self._can_format())
