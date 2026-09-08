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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mbu_gui.disks import (
    NO_DISK_ID_TEXT,
    Disk,
    Inventory,
    candidate_backup_disks,
    confirm_token,
    describe_disk,
    format_block_reason,
    suggested_set_name,
)

WIPE_WARNING = "This will erase the disk."
EMPTY_DISK_TEXT = "Plug in a new disk that is not this computer's system disk."
CONFIRM_PROMPT = "Type the confirmation code for the disk you selected"
PARTITION_HEADERS = ["device", "size", "mount", "current label"]
SET_NAME_LABEL = "Name for this backup set (your choice)"
CONFIRM_LABEL = "Confirmation code"


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

        self.diskInfoLabel = QLabel("")
        self.diskInfoLabel.setObjectName("diskInfoLabel")
        self.diskInfoLabel.setWordWrap(True)
        layout.addWidget(self.diskInfoLabel)

        self.partitionTable = QTableWidget(0, len(PARTITION_HEADERS))
        self.partitionTable.setObjectName("partitionTable")
        self.partitionTable.setHorizontalHeaderLabels(PARTITION_HEADERS)
        self.partitionTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.partitionTable.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.partitionTable)

        layout.addWidget(QLabel(SET_NAME_LABEL))
        self.psetEdit = QLineEdit()
        self.psetEdit.setObjectName("psetEdit")
        self.psetEdit.setPlaceholderText("Letters and digits only")
        layout.addWidget(self.psetEdit)

        self.confirmPromptLabel = QLabel(CONFIRM_PROMPT)
        self.confirmPromptLabel.setObjectName("confirmPromptLabel")
        self.confirmPromptLabel.setWordWrap(True)
        layout.addWidget(self.confirmPromptLabel)

        layout.addWidget(QLabel(CONFIRM_LABEL))
        self.confirmEdit = QLineEdit()
        self.confirmEdit.setObjectName("confirmEdit")
        layout.addWidget(self.confirmEdit)

        self.blockReasonLabel = QLabel("")
        self.blockReasonLabel.setObjectName("blockReasonLabel")
        self.blockReasonLabel.setWordWrap(True)
        self.blockReasonLabel.setStyleSheet(
            "background-color: #FCF3CF; color: #000000; padding: 8px;"
        )
        self.blockReasonLabel.hide()
        layout.addWidget(self.blockReasonLabel)

        buttons = QHBoxLayout()
        self.formatButton = QPushButton("Format disk")
        self.formatButton.setObjectName("formatButton")
        self.leaveButton = QPushButton("Cancel")
        self.leaveButton.setObjectName("leaveButton")
        buttons.addWidget(self.formatButton)
        buttons.addWidget(self.leaveButton)
        layout.addLayout(buttons)

        self._auto_pset = ""
        self.diskList.itemSelectionChanged.connect(self._on_selection_changed)
        self.diskList.currentItemChanged.connect(self._on_selection_changed)
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

    def block_reason(self) -> str | None:
        return format_block_reason(
            self.inventory,
            self._selected_disk(),
            self.psetEdit.text(),
            self.confirmEdit.text(),
        )

    def _can_format(self) -> bool:
        return self.block_reason() is None

    def _on_selection_changed(self, *args) -> None:
        self._autofill_pset()
        self._sync_enabled()

    def _autofill_pset(self) -> None:
        """Offer a name that already passes validation for the selected disk.

        The field started empty, so selecting a disk and typing the confirmation
        code still left the button dead with nothing on screen saying a name was
        also required. Anything the user has typed themselves is left alone.
        """
        disk = self._selected_disk()
        if disk is None:
            return
        current = self.psetEdit.text()
        if current and current != self._auto_pset:
            return
        self._auto_pset = suggested_set_name(self.inventory, disk)
        self.psetEdit.setText(self._auto_pset)

    def _sync_details(self) -> None:
        disk = self._selected_disk()
        if disk is None:
            self.diskInfoLabel.setText("")
            self.partitionTable.setRowCount(0)
            return
        self.diskInfoLabel.setText(describe_disk(disk))
        self.partitionTable.setRowCount(len(disk.partitions))
        for row, part in enumerate(disk.partitions):
            values = [part.name, part.size, part.mountpoint or "", part.partlabel or ""]
            for col, value in enumerate(values):
                self.partitionTable.setItem(row, col, QTableWidgetItem(value))

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
        # Upper case so the code cannot be mistaken for a set name: it is drawn
        # from the tail of the serial and can read like an ordinary word.
        code = (confirm_token(disk) or "").upper()
        self.confirmPromptLabel.setText(
            f"To erase {disk.size} {disk.model or disk.name} "
            f"({disk.disk_id}), type this code: {code}"
        )
        self.confirmEdit.setPlaceholderText(code)

    def _sync_enabled(self, *args) -> None:
        self._sync_prompt()
        self._sync_details()
        reason = self.block_reason()
        self.blockReasonLabel.setText(reason or "")
        self.blockReasonLabel.setVisible(reason is not None)
        self.formatButton.setEnabled(reason is None)
