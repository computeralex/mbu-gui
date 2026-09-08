from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mbu_gui.disks import (
    Inventory,
    describe_disk,
    find_disk,
    propose_labels,
    setup_block_reason,
)

SAFETY_COPY = "This only names partitions; it does not erase the disk."
ALREADY_NAMED_TEXT = (
    "Partitions already use MBU names (set {live_set}). You can leave them alone."
)
DEFAULT_SET_NAME = "main"
PREVIEW_HEADERS = ["device", "size", "mount", "current label", "proposed label"]


class SetupPage(QWidget):
    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        self.inventory = inventory

        layout = QVBoxLayout(self)

        title = QLabel("Set up this computer")
        layout.addWidget(title)

        self.safetyLabel = QLabel(SAFETY_COPY)
        self.safetyLabel.setObjectName("safetyLabel")
        self.safetyLabel.setWordWrap(True)
        layout.addWidget(self.safetyLabel)

        already = ""
        if not inventory.unnamed_live and inventory.live_set:
            already = ALREADY_NAMED_TEXT.format(live_set=inventory.live_set)
        self.alreadyNamedLabel = QLabel(already)
        self.alreadyNamedLabel.setObjectName("alreadyNamedLabel")
        self.alreadyNamedLabel.setWordWrap(True)
        self.alreadyNamedLabel.setVisible(bool(already))
        layout.addWidget(self.alreadyNamedLabel)

        # Same disk identity line the prepare page shows, so both pages state
        # which physical disk they are about to touch in the same terms.
        live = find_disk(inventory, inventory.live_disk)
        self.diskInfoLabel = QLabel(describe_disk(live) if live is not None else "")
        self.diskInfoLabel.setObjectName("diskInfoLabel")
        self.diskInfoLabel.setWordWrap(True)
        layout.addWidget(self.diskInfoLabel)

        layout.addWidget(QLabel("Set name"))
        self.setNameEdit = QLineEdit(DEFAULT_SET_NAME)
        self.setNameEdit.setObjectName("setNameEdit")
        layout.addWidget(self.setNameEdit)

        layout.addWidget(QLabel("Type the set name again to confirm"))
        self.confirmEdit = QLineEdit()
        self.confirmEdit.setObjectName("confirmEdit")
        self.confirmEdit.setPlaceholderText("Type the set name again to confirm")
        layout.addWidget(self.confirmEdit)

        self.previewTable = QTableWidget(0, len(PREVIEW_HEADERS))
        self.previewTable.setObjectName("previewTable")
        self.previewTable.setHorizontalHeaderLabels(PREVIEW_HEADERS)
        self.previewTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.previewTable.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.previewTable)

        self.blockReasonLabel = QLabel("")
        self.blockReasonLabel.setObjectName("blockReasonLabel")
        self.blockReasonLabel.setWordWrap(True)
        # A greyed-out button next to plain body text reads as a broken app, so
        # make the explanation look like the answer to "why can't I continue?".
        self.blockReasonLabel.setStyleSheet(
            "background-color: #FCF3CF; color: #000000; padding: 8px;"
        )
        self.blockReasonLabel.hide()
        layout.addWidget(self.blockReasonLabel)

        buttons = QHBoxLayout()
        self.applyButton = QPushButton("Apply names")
        self.applyButton.setObjectName("applyButton")
        leave_text = "Leave them alone" if already else "Cancel"
        self.leaveButton = QPushButton(leave_text)
        self.leaveButton.setObjectName("leaveButton")
        buttons.addWidget(self.applyButton)
        buttons.addWidget(self.leaveButton)
        layout.addLayout(buttons)

        self.setNameEdit.textChanged.connect(self._on_set_name_changed)
        self.confirmEdit.textChanged.connect(self._sync_enabled)
        self._fill_preview()
        self._sync_enabled()

    def _on_set_name_changed(self) -> None:
        self._fill_preview()
        self._sync_enabled()

    def _fill_preview(self) -> None:
        pairs = propose_labels(self.inventory, self.setNameEdit.text())
        self.previewTable.setRowCount(len(pairs))
        for row, (part, label) in enumerate(pairs):
            values = [
                part.name,
                part.size,
                part.mountpoint or "",
                part.partlabel or "",
                label,
            ]
            for col, value in enumerate(values):
                self.previewTable.setItem(row, col, QTableWidgetItem(value))

    def block_reason(self) -> str | None:
        return setup_block_reason(
            self.inventory, self.setNameEdit.text(), self.confirmEdit.text()
        )

    def _can_apply(self) -> bool:
        return self.block_reason() is None

    def _sync_enabled(self) -> None:
        reason = self.block_reason()
        self.blockReasonLabel.setText(reason or "")
        self.blockReasonLabel.setVisible(reason is not None)
        self.applyButton.setEnabled(reason is None)

    def labels_arg(self) -> str:
        name = self.setNameEdit.text()
        return ",".join(
            f"{part.name}={label}"
            for part, label in propose_labels(self.inventory, name)
        )
