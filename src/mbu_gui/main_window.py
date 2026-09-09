from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mbu_gui.backup_dialog import UNKNOWN_DESTINATION_TEXT, BackupDialog
from mbu_gui.browse_page import BrowsePage, UNMOUNT_FAIL_TEXT
from mbu_gui.disks import (
    Inventory,
    RESTART_TO_FINISH_TEXT,
    describe_backup_route,
    live_disk_unsupported,
    next_step,
)
from mbu_gui.format_page import FormatPage
from mbu_gui.helper_client import explain_helper_failure, pkexec_argv, which_helper
from mbu_gui.logs import (
    LastRun,
    current_file_from_line,
    last_run_label,
    plain_label_line,
    progress_label,
    sync_target,
)
from mbu_gui.process import LineProcess
from mbu_gui.setup_page import SetupPage

UNPLUG_BANNER_TEXT = (
    "Unplug the backup disk now.\n"
    "Duplicate UUIDs confuse Linux if you leave it plugged in."
)
UNPLUG_UNFINISHED_TEXT = (
    "The backup did not finish. Unplug the backup disk anyway.\n"
    "MBU clones UUIDs one partition at a time, so this disk may already share "
    "UUIDs with this computer. Leaving it plugged in can make Linux boot from "
    "the wrong disk."
)
COPY_NOW_TEXT = "Copy everything now"
SKIP_TEXT = "Skip"

PAGE_HOME = 0
PAGE_SETUP = 1
PAGE_FORMAT = 2
PAGE_BROWSE = 3

CLOSE_MOUNTED_TEXT = "Unmount the backup before closing."
# Not "data may be lost": this computer is never written to. What is at stake is
# the backup already on the destination disk, which MBU overwrites in place as
# it copies, so a half-finished run has damaged it without replacing it.
CANCEL_CONFIRM_TITLE = "Stop the backup?"
CANCEL_CONFIRM_TEXT = (
    "Nothing on this computer is changed by stopping.\n\n"
    "The backup disk is another matter. MBU copies over the previous backup as "
    "it goes, so that older backup is already part way overwritten and will not "
    "be bootable. Stopping now leaves the disk with neither a finished new "
    "backup nor a usable old one, and you will need to run a full backup again."
)
CANCEL_YES_TEXT = "Stop the backup"
CANCEL_NO_TEXT = "Let it finish"
CLOSE_RUNNING_TEXT = (
    "A backup is running. Closing the window would not stop it, because the "
    "copying runs with administrator rights outside this window.\n\n"
    "Stop the backup first, or let it finish."
)
CANCEL_REQUESTED_TEXT = "Stopping the backup..."
SETUP_DONE_TEXT = (
    "This computer is named and ready. Next: prepare a backup disk, which "
    "erases a spare disk and sets it up to receive backups."
)
SETUP_REBOOT_TEXT = RESTART_TO_FINISH_TEXT

_HELPER_NOUNS = {
    "backup": "backup",
    "format-disk": "format",
    "mount": "mount",
    "label-live": "label",
    "clean": "unmount",
}


def _icon_candidates() -> tuple[Path, ...]:
    repo = Path(__file__).resolve().parents[2]
    return (
        Path("/usr/share/mbu-gui/mbu-icon.png"),
        repo / "data" / "mbu-icon.png",
        repo / "vendor" / "mbu" / "mbu-icon.png",
    )


def _icon_path() -> Path | None:
    for candidate in _icon_candidates():
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
        reload_last_run: Callable[[], LastRun | None] | None = None,
        ask_copy_now: Callable[[], bool] | None = None,
        ask_cancel: Callable[[], bool] | None = None,
        start_cancel: Callable[[list[str]], None] | None = None,
        open_dir: Callable[[str], None] | None = None,
        backup_unfinished: bool = False,
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
        self.reload_last_run = reload_last_run
        self.ask_copy_now = ask_copy_now
        self.ask_cancel = ask_cancel
        self.start_cancel = start_cancel
        self._cancel_process: LineProcess | None = None
        self._cancelling = False
        self.open_dir = open_dir
        self._running = False
        self._helper_output: list[str] = []
        self._helper_kind = "backup"
        self._line_process: LineProcess | None = None
        self._backup_unfinished = backup_unfinished
        self._live_disk_usable = live_disk_unsupported(inventory) is None
        self._needs_reboot = False
        self._phases_total = 0
        self._phases_done = 0
        self._phase_files = 0
        self._phase_target = ""

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

        self._next_step = next_step(inventory)

        self.startButton = QPushButton(self._next_step.label)
        self.startButton.setObjectName("startButton")
        start_font = QFont(self.startButton.font())
        start_font.setPointSize(start_font.pointSize() + 4)
        start_font.setBold(True)
        self.startButton.setFont(start_font)
        self.startButton.setMinimumHeight(48)
        self.startButton.setEnabled(self._next_step.enabled)
        self.startButton.clicked.connect(self.on_start_clicked)
        layout.addWidget(self.startButton)

        self.blockedHeadlineLabel = QLabel("")
        self.blockedHeadlineLabel.setObjectName("blockedHeadlineLabel")
        self.blockedHeadlineLabel.setWordWrap(True)
        headline_font = QFont(self.blockedHeadlineLabel.font())
        headline_font.setPointSize(headline_font.pointSize() + 3)
        headline_font.setBold(True)
        self.blockedHeadlineLabel.setFont(headline_font)
        self.blockedHeadlineLabel.hide()
        layout.addWidget(self.blockedHeadlineLabel)

        self.startReasonLabel = QLabel(self._next_step.detail)
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

        progress_row = QHBoxLayout()
        self.progressBar = QProgressBar()
        self.progressBar.setObjectName("progressBar")
        self.progressBar.setTextVisible(True)
        self.cancelButton = QPushButton("Stop")
        self.cancelButton.setObjectName("cancelButton")
        self.cancelButton.clicked.connect(self.on_cancel_clicked)
        progress_row.addWidget(self.progressBar, 1)
        progress_row.addWidget(self.cancelButton)
        self.progressBar.hide()
        self.cancelButton.hide()

        self.currentFileLabel = QLabel("")
        self.currentFileLabel.setObjectName("currentFileLabel")
        # A deep path is wider than the window, and a label reports its full
        # text width as its preferred size, so the layout grew the window on
        # every longer path. Ignore that preference and shorten the text to fit.
        self.currentFileLabel.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.currentFileLabel.setMinimumWidth(0)
        self._current_file = ""

        self.logView = QPlainTextEdit()
        self.logView.setObjectName("logView")
        self.logView.setReadOnly(True)
        self.logView.setMinimumHeight(160)
        self.logView.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.logView.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )

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
        if backup_unfinished:
            self.show_unplug(True, text=UNPLUG_UNFINISHED_TEXT)

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

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(self.stack, 1)
        root_layout.addLayout(progress_row)
        root_layout.addWidget(self.currentFileLabel)
        root_layout.addWidget(self.logView)
        root_layout.addWidget(self.unplugBanner)
        self.setCentralWidget(root)
        self.resize(720, 560)

        # One code path decides the primary button on first paint and on every
        # refresh, so the opening screen cannot disagree with a later one.
        self._sync_next_step()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self._on_home_timer)
        self._refresh_timer.start()

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

    def _sync_next_step(self) -> None:
        if self._needs_reboot and self.inventory.unnamed_live:
            # Covers the moment between naming and the next inventory reload,
            # before the machine record has been consulted again.
            self.inventory = replace(self.inventory, awaiting_restart=True)
        step = next_step(self.inventory)
        self._next_step = step
        self.startButton.setText(step.label)
        self.startReasonLabel.setText(step.detail)
        # A blocked state has no action behind it, so show the reason instead of
        # a large dead button suggesting something that cannot be done.
        blocked = step.action == "blocked"
        self.startButton.setVisible(not blocked)
        self.blockedHeadlineLabel.setText(step.headline)
        self.blockedHeadlineLabel.setVisible(blocked and bool(step.headline))
        # Naming and preparing are pointless when this computer can never be a
        # source, and entering those pages was the loop the user got stuck in.
        usable = live_disk_unsupported(self.inventory) is None
        self._live_disk_usable = usable
        if not self._running:
            self.startButton.setEnabled(step.enabled)
            self.setupButton.setEnabled(usable)
            self.formatButton.setEnabled(usable)

    def _apply_inventory(self, inventory: Inventory) -> None:
        self.inventory = inventory
        self.statusLabel.setText(inventory.status_line)
        self._sync_next_step()
        self._replace_setup_page(inventory)
        self._replace_format_page(inventory)
        self._replace_browse_page(inventory)

    def _apply_last_run(self, last_run: LastRun | None) -> None:
        self.last_run = last_run
        self.lastRunLabel.setText(last_run_label(last_run))

    def refresh(self) -> None:
        if self._running:
            return
        if self.browsePage.mounted:
            return
        if self.reload_inventory is not None:
            try:
                self._apply_inventory(self.reload_inventory())
            except Exception as e:
                self.show_error(str(e))
        if self.reload_last_run is not None:
            try:
                self._apply_last_run(self.reload_last_run())
            except Exception as e:
                self.show_error(str(e))

    def _on_home_timer(self) -> None:
        if self.stack.currentIndex() != PAGE_HOME:
            return
        self.refresh()

    def _go_home(self) -> None:
        self.stack.setCurrentIndex(PAGE_HOME)
        self.refresh()

    def _explain_failure(self, code: int, stderr: str = "") -> str:
        return explain_helper_failure(
            code,
            stderr,
            helper_exists=self.helper_exists,
            pkexec_exists=self.pkexec_exists,
            noun=_HELPER_NOUNS.get(self._helper_kind, "backup"),
        )

    def on_cancel_clicked(self) -> None:
        if not self._running or self._cancelling:
            return
        if not self._confirm_cancel():
            return
        self._cancelling = True
        self.cancelButton.setEnabled(False)
        self.progressBar.setFormat(CANCEL_REQUESTED_TEXT)
        self.append_log(CANCEL_REQUESTED_TEXT)
        self._send_cancel()

    def _confirm_cancel(self) -> bool:
        if self.ask_cancel is not None:
            return self.ask_cancel()
        box = QMessageBox(self)
        box.setObjectName("cancelConfirm")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(CANCEL_CONFIRM_TITLE)
        box.setText(CANCEL_CONFIRM_TEXT)
        stop = box.addButton(CANCEL_YES_TEXT, QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton(CANCEL_NO_TEXT, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(keep)
        box.exec()
        return box.clickedButton() is stop

    def _send_cancel(self) -> None:
        helper = self.helper_path if self.helper_path is not None else which_helper()
        if helper is None or not self.helper_exists or not self.pkexec_exists:
            self.show_error(self._missing_helper_message(helper is not None))
            return
        argv = pkexec_argv(helper, ["cancel"])
        if self.start_cancel is not None:
            self.start_cancel(argv)
            return
        proc = LineProcess(self)
        self._cancel_process = proc
        proc.line.connect(self.append_log)
        proc.start(argv)

    def closeEvent(self, event) -> None:
        if self._running:
            # Closing the window does not stop root's rsync, so pretending it
            # does would be worse than refusing. Say what is actually running.
            self.show_error(CLOSE_RUNNING_TEXT)
            if not self._cancelling:
                self.on_cancel_clicked()
            event.ignore()
            return
        if self.browsePage.mounted:
            self.show_error(CLOSE_MOUNTED_TEXT)
            event.ignore()
            return
        super().closeEvent(event)

    def show_unplug(self, visible: bool, *, text: str = UNPLUG_BANNER_TEXT) -> None:
        self.unplugBanner.setText(text)
        self.unplugBanner.setVisible(visible)

    def _clear_unplug(self) -> None:
        """Hide the banner unless a backup may have left UUIDs cloned.

        Format, mount and unmount do not clone UUIDs, so they hide the banner
        when they fail. They must not erase a still-standing warning from a
        backup that never finished.
        """
        if self._backup_unfinished:
            self.show_unplug(True, text=UNPLUG_UNFINISHED_TEXT)
            return
        self.show_unplug(False)

    def append_log(self, line: str) -> None:
        self.logView.appendPlainText(line)
        current = current_file_from_line(line)
        if current is not None:
            self.show_current_file(current)

    def _start_progress(self, fselection: str) -> None:
        # The requested functions tell us how many partitions MBU will copy, so
        # the bar can be a real fraction rather than a spinner. Flags such as
        # -bootfix are instructions, not partitions, and must not be counted.
        self._phases_total = len(
            [f for f in fselection.split(",") if f and not f.startswith("-")]
        )
        self._phases_done = 0
        self._phase_files = 0
        self._phase_target = ""
        self.progressBar.setMaximum(max(self._phases_total, 1))
        self.progressBar.setValue(0)
        self.progressBar.setFormat("Starting")
        self.progressBar.show()
        self._cancelling = False
        self.cancelButton.setEnabled(True)
        self.cancelButton.show()

    def _finish_progress(self, ok: bool) -> None:
        self.cancelButton.hide()
        if not ok:
            self.progressBar.hide()
            return
        self.progressBar.setMaximum(1)
        self.progressBar.setValue(1)
        self.progressBar.setFormat("Backup finished")

    def show_current_file(self, text: str) -> None:
        self._current_file = text
        self._elide_current_file()

    def _elide_current_file(self) -> None:
        room = self.currentFileLabel.width()
        if room <= 1:
            # Before the first layout pass there is no width to fit into.
            self.currentFileLabel.setText(self._current_file)
            return
        metrics = QFontMetrics(self.currentFileLabel.font())
        self.currentFileLabel.setText(
            metrics.elidedText(self._current_file, Qt.TextElideMode.ElideMiddle, room)
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide_current_file()

    def show_error(self, message: str) -> None:
        self.append_log(message)
        if not self._running:
            self.startButton.setEnabled(self._next_step.enabled)

    def set_running(self, running: bool) -> None:
        self._running = running
        idle = not running
        self.setupButton.setEnabled(idle and self._live_disk_usable)
        self.formatButton.setEnabled(idle and self._live_disk_usable)
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
            self.startButton.setEnabled(self._next_step.enabled)
            self.setupPage.leaveButton.setEnabled(True)
            self.setupPage._sync_enabled()
            self.formatPage.leaveButton.setEnabled(True)
            self.formatPage._sync_enabled()
            self.browsePage._sync_enabled()

    def on_start_clicked(self) -> None:
        if self._running:
            return
        action = self._next_step.action
        if action == "setup":
            self.stack.setCurrentIndex(PAGE_SETUP)
            return
        if action == "format":
            self.stack.setCurrentIndex(PAGE_FORMAT)
            return
        if action != "backup":
            return
        dialog = BackupDialog(self.inventory, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.route is None:
            self.show_error(UNKNOWN_DESTINATION_TEXT)
            return
        self._run_backup_with_fselection(dialog.fselection())

    def on_setup_clicked(self) -> None:
        if self._running:
            return
        self.stack.setCurrentIndex(PAGE_SETUP)

    def on_setup_leave(self) -> None:
        self._go_home()

    def on_setup_apply(self) -> None:
        if self._running or not self.setupPage._can_apply():
            return
        self._run_label_live(self.setupPage.labels_arg())

    def on_format_clicked(self) -> None:
        if self._running:
            return
        self.stack.setCurrentIndex(PAGE_FORMAT)

    def on_format_leave(self) -> None:
        self._go_home()

    def on_format_apply(self) -> None:
        if self._running or not self.formatPage._can_format():
            return
        name = self.formatPage.selected_disk_name()
        disk_id = self.formatPage.selected_disk_id()
        if name is None or disk_id is None:
            return
        self._run_format_disk(name, disk_id, self.formatPage.psetEdit.text())

    def on_browse_clicked(self) -> None:
        if self._running:
            return
        self.stack.setCurrentIndex(PAGE_BROWSE)

    def on_browse_leave(self) -> None:
        self._go_home()

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

    def _missing_helper_message(self, helper_ok: bool) -> str:
        return explain_helper_failure(
            127,
            "",
            helper_exists=helper_ok,
            pkexec_exists=self.pkexec_exists,
            noun=_HELPER_NOUNS.get(self._helper_kind, "backup"),
        )

    def _run_backup_with_fselection(self, fselection: str) -> None:
        if self._running:
            return
        self._helper_kind = "backup"
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(self._missing_helper_message(helper_ok))
            return
        argv = pkexec_argv(helper, ["backup", "--fselection", fselection])
        self._helper_output = []
        self._start_progress(fselection)
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
        self._helper_kind = "label-live"
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(self._missing_helper_message(helper_ok))
            self._go_home()
            return
        argv = pkexec_argv(helper, ["label-live", "--labels", labels])
        self._helper_output = []
        self.set_running(True)
        if self.start_process is not None:
            self.start_process(argv)
            return
        proc = LineProcess(self)
        self._line_process = proc
        proc.line.connect(self._on_helper_line)
        proc.finished.connect(self._on_process_finished)
        proc.start(argv)

    def _run_format_disk(self, disk: str, disk_id: str, pset: str) -> None:
        if self._running:
            return
        self._helper_kind = "format-disk"
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(self._missing_helper_message(helper_ok))
            self._go_home()
            return
        argv = pkexec_argv(
            helper,
            ["format-disk", "--disk", disk, "--disk-id", disk_id, "--pset", pset],
        )
        self._helper_output = []
        self._clear_unplug()
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
        self._helper_kind = "mount"
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(self._missing_helper_message(helper_ok))
            self._go_home()
            return
        argv = pkexec_argv(helper, ["mount", "--set", set_name])
        self._helper_output = []
        self._clear_unplug()
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
        self._helper_kind = "clean"
        helper = self.helper_path if self.helper_path is not None else which_helper()
        helper_ok = self.helper_exists and helper is not None
        if helper is None or not helper_ok or not self.pkexec_exists:
            self.show_error(self._missing_helper_message(helper_ok))
            self._go_home()
            return
        argv = pkexec_argv(helper, ["clean"])
        self._helper_output = []
        self._clear_unplug()
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
        if self._helper_kind == "label-live":
            shown = plain_label_line(text)
            if shown is not None:
                self.append_log(shown)
            return
        if self._helper_kind == "backup":
            self._track_progress(text)
        self.append_log(text)

    def _track_progress(self, text: str) -> None:
        target = sync_target(text)
        if target is not None:
            self._phases_done += 1
            self._phase_target = target
            self._phase_files = 0
        elif current_file_from_line(text) is not None:
            self._phase_files += 1
        else:
            return
        total = max(self._phases_total, self._phases_done)
        self.progressBar.setMaximum(total)
        self.progressBar.setValue(max(self._phases_done - 1, 0))
        self.progressBar.setFormat(
            progress_label(
                self._phases_done, total, self._phase_target, self._phase_files
            )
        )

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
        self._finish_progress(code == 0)
        if code == 0:
            self._backup_unfinished = False
            self.show_unplug(True)
            self.set_running(False)
            self.refresh()
            return
        self.show_error(self._explain_failure(code, stderr))
        # A backup that got as far as running may already have cloned UUIDs, so
        # the disk still has to come out even though the run failed.
        self._backup_unfinished = True
        self.show_unplug(True, text=UNPLUG_UNFINISHED_TEXT)
        self.set_running(False)

    def on_label_live_finished(self, code: int, stderr: str = "") -> None:
        if code != 0:
            self.show_error(self._explain_failure(code, stderr))
            self.set_running(False)
            self._go_home()
            return
        self.set_running(False)
        self._go_home()
        # The names are on the disk, but the kernel cannot re-read the table of
        # the disk it is running from. If udev did not pick the new names up we
        # must say so, because offering "Set up this computer" again is the loop
        # that made the app look broken.
        if self.inventory.unnamed_live:
            self._needs_reboot = True
            self._sync_next_step()
            self.append_log(SETUP_REBOOT_TEXT)
            return
        self.append_log(SETUP_DONE_TEXT)

    def on_format_finished(self, code: int, stderr: str = "") -> None:
        if code != 0:
            self.show_error(self._explain_failure(code, stderr))
            self._clear_unplug()
            self.set_running(False)
            self._go_home()
            return
        self.set_running(False)
        self.refresh()
        if describe_backup_route(self.inventory) is not None and self._ask_copy_now():
            self.stack.setCurrentIndex(PAGE_HOME)
            self._run_backup_with_fselection(
                "-bootfix," + ",".join(self.inventory.live_functions)
            )
            return
        # Formatting runs bare mkfs, so the new filesystems get fresh random
        # UUIDs and nothing is cloned yet. Telling the user to unplug here is
        # both untrue and the opposite of what they need to do next, which is
        # to back up onto the disk they just prepared.
        self._clear_unplug()
        self.stack.setCurrentIndex(PAGE_HOME)

    def on_mount_finished(self, code: int, stderr: str = "") -> None:
        if code == 0:
            self.browsePage.set_mounted(True)
            self.browsePage.busyLabel.setText("")
            self.set_running(False)
            return
        message = self._explain_failure(code, stderr)
        self.browsePage.busyLabel.setText(message)
        self.show_error(message)
        self.browsePage.set_mounted(False)
        self._clear_unplug()
        self.set_running(False)

    def on_unmount_finished(self, code: int) -> None:
        if code != 0:
            self.browsePage.busyLabel.setText(UNMOUNT_FAIL_TEXT)
            self._clear_unplug()
            self.set_running(False)
            return
        self.browsePage.busyLabel.setText("")
        self.browsePage.set_mounted(False)
        self.set_running(False)
        self.show_unplug(True)
        self._go_home()

    def _ask_copy_now(self) -> bool:
        if self.ask_copy_now is not None:
            return self.ask_copy_now()
        route = describe_backup_route(self.inventory)
        box = QMessageBox(self)
        box.setWindowTitle("Backup disk ready")
        box.setText(
            "Copy everything from this computer onto the new backup disk?\n\n"
            f"{route}"
        )
        copy_btn = box.addButton(COPY_NOW_TEXT, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(SKIP_TEXT, QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() == copy_btn
