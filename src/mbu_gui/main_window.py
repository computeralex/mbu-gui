from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mbu_gui.backup_dialog import BackupDialog
from mbu_gui.browse_page import BrowsePage, UNMOUNT_FAIL_TEXT
from mbu_gui.disks import Inventory
from mbu_gui.format_page import FormatPage
from mbu_gui.helper_client import explain_helper_failure, pkexec_argv, which_helper
from mbu_gui.logs import LastRun, current_file_from_line, last_run_label
from mbu_gui.process import LineProcess
from mbu_gui.setup_page import SetupPage

UNPLUG_BANNER_TEXT = (
    "Unplug the backup disk now.\n"
    "Duplicate UUIDs confuse Linux if you leave it plugged in."
)
COPY_NOW_TEXT = "Copy everything now"
SKIP_TEXT = "Skip"

PAGE_HOME = 0
PAGE_SETUP = 1
PAGE_FORMAT = 2
PAGE_BROWSE = 3


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
        start_process: Callable[[list[str]], None] | None = None,
        helper_path: Path | None = None,
        reload_inventory: Callable[[], Inventory] | None = None,
        ask_copy_now: Callable[[], bool] | None = None,
        open_dir: Callable[[str], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.inventory = inventory
        self.last_run = last_run
        self.helper_exists = helper_exists
        self.pkexec_exists = pkexec_exists
        self.start_process = start_process
        self.helper_path = helper_path
        self.reload_inventory = reload_inventory
        self.ask_copy_now = ask_copy_now
        self.open_dir = open_dir
        self._running = False
        self._helper_output: list[str] = []
        self._helper_kind = "backup"
        self._line_process: LineProcess | None = None

        self.setWindowTitle("MBU Backup")
        icon = _icon_path()
        if icon is not None:
            self.setWindowIcon(QIcon(str(icon)))

        self.homePage = QWidget()
        self.homePage.setObjectName("homePage")
        layout = QVBoxLayout(self.homePage)

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
        self.startButton.clicked.connect(self.on_start_clicked)
        layout.addWidget(self.startButton)

        self.startReasonLabel = QLabel(inventory.start_blocked_reason or "")
        self.startReasonLabel.setObjectName("startReasonLabel")
        self.startReasonLabel.setWordWrap(True)
        layout.addWidget(self.startReasonLabel)

        secondary = QHBoxLayout()
        self.setupButton = QPushButton("Set up this computer")
        self.setupButton.setObjectName("setupButton")
        self.setupButton.clicked.connect(self.on_setup_clicked)
        self.formatButton = QPushButton("Prepare a backup disk")
        self.formatButton.setObjectName("formatButton")
        self.formatButton.clicked.connect(self.on_format_clicked)
        self.browseButton = QPushButton("Browse a backup")
        self.browseButton.setObjectName("browseButton")
        self.browseButton.clicked.connect(self.on_browse_clicked)
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

        self.setupPage = SetupPage(inventory)
        self.setupPage.setObjectName("setupPage")
        self._wire_setup_page()

        self.formatPage = FormatPage(inventory)
        self.formatPage.setObjectName("formatPage")
        self._wire_format_page()
        self.browsePage = BrowsePage(inventory, open_dir=open_dir)
        self.browsePage.setObjectName("browsePage")
        self._wire_browse_page()

        self.stack = QStackedWidget()
        self.stack.setObjectName("stack")
        self.stack.addWidget(self.homePage)
        self.stack.addWidget(self.setupPage)
        self.stack.addWidget(self.formatPage)
        self.stack.addWidget(self.browsePage)

        self.setCentralWidget(self.stack)
        self.resize(720, 560)

    def _wire_setup_page(self) -> None:
        self.setupPage.applyButton.clicked.connect(self.on_setup_apply)
        self.setupPage.leaveButton.clicked.connect(self.on_setup_leave)

    def _wire_format_page(self) -> None:
        self.formatPage.formatButton.clicked.connect(self.on_format_apply)
        self.formatPage.leaveButton.clicked.connect(self.on_format_leave)

    def _wire_browse_page(self) -> None:
        self.browsePage.mountButton.clicked.connect(self.on_mount_apply)
        self.browsePage.openButton.clicked.connect(self.on_open_clicked)
        self.browsePage.unmountButton.clicked.connect(self.on_unmount_apply)
        self.browsePage.leaveButton.clicked.connect(self.on_browse_leave)

    def _replace_setup_page(self, inventory: Inventory) -> None:
        old = self.setupPage
        page_index = self.stack.indexOf(old)
        current = self.stack.currentIndex()
        self.setupPage = SetupPage(inventory)
        self.setupPage.setObjectName("setupPage")
        self._wire_setup_page()
        if page_index < 0:
            self.stack.insertWidget(PAGE_SETUP, self.setupPage)
        else:
            self.stack.insertWidget(page_index, self.setupPage)
            self.stack.removeWidget(old)
        old.deleteLater()
        if current == PAGE_SETUP:
            self.stack.setCurrentIndex(PAGE_SETUP)

    def _replace_format_page(self, inventory: Inventory) -> None:
        old = self.formatPage
        page_index = self.stack.indexOf(old)
        current = self.stack.currentIndex()
        self.formatPage = FormatPage(inventory)
        self.formatPage.setObjectName("formatPage")
        self._wire_format_page()
        if page_index < 0:
            self.stack.insertWidget(PAGE_FORMAT, self.formatPage)
        else:
            self.stack.insertWidget(page_index, self.formatPage)
            self.stack.removeWidget(old)
        old.deleteLater()
        if current == PAGE_FORMAT:
            self.stack.setCurrentIndex(PAGE_FORMAT)

    def _replace_browse_page(self, inventory: Inventory) -> None:
        old = self.browsePage
        page_index = self.stack.indexOf(old)
        current = self.stack.currentIndex()
        self.browsePage = BrowsePage(inventory, open_dir=self.open_dir)
        self.browsePage.setObjectName("browsePage")
        self._wire_browse_page()
        if page_index < 0:
            self.stack.insertWidget(PAGE_BROWSE, self.browsePage)
        else:
            self.stack.insertWidget(page_index, self.browsePage)
            self.stack.removeWidget(old)
        old.deleteLater()
        if current == PAGE_BROWSE:
            self.stack.setCurrentIndex(PAGE_BROWSE)

    def _apply_inventory(self, inventory: Inventory) -> None:
        self.inventory = inventory
        self.statusLabel.setText(inventory.status_line)
        self.startReasonLabel.setText(inventory.start_blocked_reason or "")
        if not self._running:
            self.startButton.setEnabled(inventory.start_blocked_reason is None)
        self._replace_setup_page(inventory)
        self._replace_format_page(inventory)
        self._replace_browse_page(inventory)

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
            self.setupPage.applyButton.setEnabled(False)
            self.setupPage.leaveButton.setEnabled(False)
            self.formatPage.formatButton.setEnabled(False)
            self.formatPage.leaveButton.setEnabled(False)
            self.browsePage.mountButton.setEnabled(False)
            self.browsePage.openButton.setEnabled(False)
            self.browsePage.unmountButton.setEnabled(False)
            self.browsePage.leaveButton.setEnabled(False)
        else:
            self.startButton.setEnabled(self.inventory.start_blocked_reason is None)
            self.setupPage.leaveButton.setEnabled(True)
            self.setupPage._sync_enabled()
            self.formatPage.leaveButton.setEnabled(True)
            self.formatPage._sync_enabled()
            self.browsePage._sync_enabled()

    def on_start_clicked(self) -> None:
        if self.inventory.start_blocked_reason or self._running:
            return
        dialog = BackupDialog(self.inventory, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._run_backup_with_fselection(dialog.fselection())

    def on_setup_clicked(self) -> None:
        if self._running:
            return
        self.stack.setCurrentIndex(PAGE_SETUP)

    def on_setup_leave(self) -> None:
        self.stack.setCurrentIndex(PAGE_HOME)

    def on_setup_apply(self) -> None:
        if self._running or not self.setupPage._can_apply():
            return
        self._run_label_live(self.setupPage.labels_arg())

    def on_format_clicked(self) -> None:
        if self._running:
            return
        self.stack.setCurrentIndex(PAGE_FORMAT)

    def on_format_leave(self) -> None:
        self.stack.setCurrentIndex(PAGE_HOME)

    def on_format_apply(self) -> None:
        if self._running or not self.formatPage._can_format():
            return
        name = self.formatPage.selected_disk_name()
        if name is None:
            return
        self._run_format_disk(name, self.formatPage.psetEdit.text())

    def on_browse_clicked(self) -> None:
        if self._running:
            return
        self.stack.setCurrentIndex(PAGE_BROWSE)

    def on_browse_leave(self) -> None:
        self.stack.setCurrentIndex(PAGE_HOME)

    def on_mount_apply(self) -> None:
        if self._running or self.browsePage.mounted:
            return
        name = self.browsePage.selected_set_name()
        if name is None:
            return
        self._run_mount(name)

    def on_open_clicked(self) -> None:
        if not self.browsePage.mounted:
            return
        try:
            self.browsePage.open_mount_dir()
        except OSError as e:
            self.show_error(str(e))

    def on_unmount_apply(self) -> None:
        if self._running or not self.browsePage.mounted:
            return
        self._run_unmount()

    def _run_backup_with_fselection(self, fselection: str) -> None:
        if self._running:
            return
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(
                explain_helper_failure(
                    127,
                    "",
                    helper_exists=helper_ok,
                    pkexec_exists=self.pkexec_exists,
                )
            )
            return
        argv = pkexec_argv(helper, ["backup", "--fselection", fselection])
        self._helper_output = []
        self._helper_kind = "backup"
        self.show_unplug(False)
        self.set_running(True)
        if self.start_process is not None:
            self.start_process(argv)
            return
        proc = LineProcess(self)
        self._line_process = proc
        proc.line.connect(self._on_helper_line)
        proc.finished.connect(self._on_process_finished)
        proc.start(argv)

    def _run_label_live(self, labels: str) -> None:
        if self._running:
            return
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(
                explain_helper_failure(
                    127,
                    "",
                    helper_exists=helper_ok,
                    pkexec_exists=self.pkexec_exists,
                )
            )
            self.stack.setCurrentIndex(PAGE_HOME)
            return
        argv = pkexec_argv(helper, ["label-live", "--labels", labels])
        self._helper_output = []
        self._helper_kind = "label-live"
        self.set_running(True)
        if self.start_process is not None:
            self.start_process(argv)
            return
        proc = LineProcess(self)
        self._line_process = proc
        proc.line.connect(self._on_helper_line)
        proc.finished.connect(self._on_process_finished)
        proc.start(argv)

    def _run_format_disk(self, disk: str, pset: str) -> None:
        if self._running:
            return
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(
                explain_helper_failure(
                    127,
                    "",
                    helper_exists=helper_ok,
                    pkexec_exists=self.pkexec_exists,
                )
            )
            self.stack.setCurrentIndex(PAGE_HOME)
            return
        argv = pkexec_argv(helper, ["format-disk", "--disk", disk, "--pset", pset])
        self._helper_output = []
        self._helper_kind = "format-disk"
        self.show_unplug(False)
        self.set_running(True)
        if self.start_process is not None:
            self.start_process(argv)
            return
        proc = LineProcess(self)
        self._line_process = proc
        proc.line.connect(self._on_helper_line)
        proc.finished.connect(self._on_process_finished)
        proc.start(argv)

    def _run_mount(self, set_name: str) -> None:
        if self._running:
            return
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(
                explain_helper_failure(
                    127,
                    "",
                    helper_exists=helper_ok,
                    pkexec_exists=self.pkexec_exists,
                )
            )
            self.stack.setCurrentIndex(PAGE_HOME)
            return
        argv = pkexec_argv(helper, ["mount", "--set", set_name])
        self._helper_output = []
        self._helper_kind = "mount"
        self.show_unplug(False)
        self.set_running(True)
        if self.start_process is not None:
            self.start_process(argv)
            return
        proc = LineProcess(self)
        self._line_process = proc
        proc.line.connect(self._on_helper_line)
        proc.finished.connect(self._on_process_finished)
        proc.start(argv)

    def _run_unmount(self) -> None:
        if self._running:
            return
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(
                explain_helper_failure(
                    127,
                    "",
                    helper_exists=helper_ok,
                    pkexec_exists=self.pkexec_exists,
                )
            )
            self.stack.setCurrentIndex(PAGE_HOME)
            return
        argv = pkexec_argv(helper, ["clean"])
        self._helper_output = []
        self._helper_kind = "clean"
        self.show_unplug(False)
        self.set_running(True)
        if self.start_process is not None:
            self.start_process(argv)
            return
        proc = LineProcess(self)
        self._line_process = proc
        proc.line.connect(self._on_helper_line)
        proc.finished.connect(self._on_process_finished)
        proc.start(argv)

    def _on_helper_line(self, text: str) -> None:
        self._helper_output.append(text)
        self.append_log(text)

    def _on_process_finished(self, code: int) -> None:
        stderr = "\n".join(self._helper_output)
        if self._helper_kind == "label-live":
            self.on_label_live_finished(code, stderr)
        elif self._helper_kind == "format-disk":
            self.on_format_finished(code, stderr)
        elif self._helper_kind == "mount":
            self.on_mount_finished(code, stderr)
        elif self._helper_kind == "clean":
            self.on_unmount_finished(code)
        else:
            self.on_helper_finished(code, stderr)

    def on_helper_finished(self, code: int, stderr: str = "") -> None:
        if code == 0:
            self.show_unplug(True)
            self.set_running(False)
            return
        self.show_error(
            explain_helper_failure(
                code,
                stderr,
                helper_exists=self.helper_exists,
                pkexec_exists=self.pkexec_exists,
            )
        )
        self.show_unplug(False)
        self.set_running(False)

    def on_label_live_finished(self, code: int, stderr: str = "") -> None:
        if code == 0:
            if self.reload_inventory is not None:
                try:
                    self._apply_inventory(self.reload_inventory())
                except Exception as e:
                    self.show_error(str(e))
            self.stack.setCurrentIndex(PAGE_HOME)
            self.set_running(False)
            return
        self.show_error(
            explain_helper_failure(
                code,
                stderr,
                helper_exists=self.helper_exists,
                pkexec_exists=self.pkexec_exists,
            )
        )
        self.stack.setCurrentIndex(PAGE_HOME)
        self.set_running(False)

    def on_format_finished(self, code: int, stderr: str = "") -> None:
        if code != 0:
            self.show_error(
                explain_helper_failure(
                    code,
                    stderr,
                    helper_exists=self.helper_exists,
                    pkexec_exists=self.pkexec_exists,
                )
            )
            self.show_unplug(False)
            self.stack.setCurrentIndex(PAGE_HOME)
            self.set_running(False)
            return
        self.set_running(False)
        if self.reload_inventory is not None:
            try:
                self._apply_inventory(self.reload_inventory())
            except Exception as e:
                self.show_error(str(e))
        if self._ask_copy_now():
            self.stack.setCurrentIndex(PAGE_HOME)
            self._run_backup_with_fselection(
                "-bootfix," + ",".join(self.inventory.live_functions)
            )
            return
        self.show_unplug(True)
        self.stack.setCurrentIndex(PAGE_HOME)

    def on_mount_finished(self, code: int, stderr: str = "") -> None:
        if code == 0:
            self.browsePage.set_mounted(True)
            self.browsePage.busyLabel.setText("")
            self.set_running(False)
            return
        message = explain_helper_failure(
            code,
            stderr,
            helper_exists=self.helper_exists,
            pkexec_exists=self.pkexec_exists,
        )
        self.browsePage.busyLabel.setText(message)
        self.show_error(message)
        self.browsePage.set_mounted(False)
        self.show_unplug(False)
        self.set_running(False)

    def on_unmount_finished(self, code: int) -> None:
        if code != 0:
            self.browsePage.busyLabel.setText(UNMOUNT_FAIL_TEXT)
            self.show_unplug(False)
            self.set_running(False)
            return
        self.browsePage.busyLabel.setText("")
        self.browsePage.set_mounted(False)
        self.set_running(False)
        self.show_unplug(True)
        self.stack.setCurrentIndex(PAGE_HOME)

    def _ask_copy_now(self) -> bool:
        if self.ask_copy_now is not None:
            return self.ask_copy_now()
        box = QMessageBox(self)
        box.setWindowTitle("Backup disk ready")
        box.setText("Copy everything from this computer onto the new backup disk?")
        copy_btn = box.addButton(COPY_NOW_TEXT, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(SKIP_TEXT, QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() == copy_btn
