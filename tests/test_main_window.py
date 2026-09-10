# tests/test_main_window.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import replace
from pathlib import Path
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QSizePolicy

from mbu_gui.disks import load_lsblk
from mbu_gui.logs import LastRun
from mbu_gui.main_window import (
    PAGE_FORMAT,
    PAGE_HOME,
    PAGE_SETUP,
    PAGE_WIZARD_FINISH,
    PAGE_WIZARD_INTRO,
    MainWindow,
    _icon_candidates,
    window_size_for_screen,
)

FIXTURES = Path(__file__).parent / "fixtures"
_app = None


def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app


def test_window_opens_with_backup_ready():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    assert w.windowTitle() == "MBU Backup"
    assert w.statusLabel.text() == "Backup disk `bak1` is connected"
    assert w.lastRunLabel.text() == "No backup yet"
    assert w.startButton.isEnabled()
    assert w.startButton.text() == "Back up now"
    # The primary button always states what it is about to write to.
    assert "bak1" in w.startReasonLabel.text()
    assert w.unplugBanner.isHidden()


def test_unnamed_computer_offers_the_wizard_instead_of_a_dead_button():
    """An unprepared computer must get a live button, not a greyed-out one.

    A disabled Start Backup with the explanation in a separate label reads as
    a broken app. There is more than one step left here, so the button opens
    the guided run rather than dropping the user on one page of it.
    """
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    assert w.startButton.isEnabled()
    assert w.startButton.text() == "Take me through it"
    assert "nothing is erased" in w.startReasonLabel.text()
    w.startButton.click()
    assert w.stack.currentIndex() == PAGE_WIZARD_INTRO
    w.wizardIntroPage.startButton.click()
    assert w.stack.currentIndex() == PAGE_SETUP
    assert w.setupPage.stepLabel.text() == "Step 1 of 3"


def test_unsupported_computer_shows_no_button_at_all():
    """An MBR system disk is a dead end, so the app must not offer a button.

    The earlier build showed a giant greyed-out "Back up now", which reads as
    the app suggesting the one thing this computer can never do. There is also
    no point letting the user into the naming or prepare pages, since neither
    can make an MBR install backable.
    """
    app()
    inv = load_lsblk((FIXTURES / "lsblk_mbr_live.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    assert w.startButton.isHidden()
    assert w.blockedHeadlineLabel.isVisible()
    assert w.blockedHeadlineLabel.text() == "This computer cannot be backed up"
    assert "MBR" in w.startReasonLabel.text()
    assert "UEFI" in w.startReasonLabel.text()
    assert not w.setupButton.isEnabled()
    assert not w.formatButton.isEnabled()
    # Reading an existing backup is unaffected by the live disk's layout.
    assert w.browseButton.isEnabled()


def test_missing_backup_disk_offers_prepare_and_says_to_replug():
    """The dead end that made the app look broken after a reboot.

    Preparing a disk and then unplugging it left Start Backup greyed with the
    reason easy to miss, so the button now offers the way out and the text
    names replugging as the fix.
    """
    app()
    from dataclasses import replace

    named = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    inv = replace(named, backup_sets=[], start_blocked_reason="Plug in the backup disk")
    w = MainWindow(inventory=inv, last_run=None)
    assert w.startButton.isEnabled()
    assert w.startButton.text() == "Take me through it"
    assert "plug in the disk you already prepared" in w.startReasonLabel.text().lower()
    w.startButton.click()
    w.wizardIntroPage.startButton.click()
    assert w.stack.currentIndex() == PAGE_FORMAT
    # Naming is already done, so the counter must not restart at one.
    assert w.formatPage.stepLabel.text() == "Step 2 of 3"
    assert "already named" in w.wizardIntroPage.resumeLabel.text()


def test_naming_reports_plainly_and_says_what_comes_next():
    """Setup used to end with six lines of raw sfdisk output and no verdict."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    named = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, reload_inventory=lambda: named)
    w._helper_kind = "label-live"
    for line in (
        "Partition name changed from '' to 'main-efi'.",
        "The partition table has been altered.",
        "Re-reading the partition table failed.: Device or resource busy",
        "Syncing disks.",
    ):
        w._on_helper_line(line)
    log = w.logView.toPlainText()
    assert "Named this computer's main-efi partition" in log
    assert "ioctl" not in log and "Device or resource busy" not in log
    w.on_label_live_finished(0)
    assert "prepare a backup disk" in w.logView.toPlainText()


def test_names_the_kernel_cannot_see_yet_ask_for_a_restart():
    """The loop that made the app unusable.

    If udev does not pick the new names up, the inventory still reads unnamed,
    and the old build answered by offering "Set up this computer" again on work
    the user had already done.
    """
    app()
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, reload_inventory=lambda: inv)
    w.on_label_live_finished(0)
    assert w.startButton.isHidden()
    assert w.blockedHeadlineLabel.text() == "Restart this computer to finish"
    assert "restart" in w.startReasonLabel.text().lower()
    assert "do not need to set up this computer a second time" in w.startReasonLabel.text()
    assert w._next_step.action == "blocked"


def _runnable_window(inv):
    """A window whose backup path reaches the helper instead of erroring out."""
    return MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: None,
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
    )


def test_the_wizard_walks_setup_then_prepare_then_the_backup_choice():
    """One pass, without the user being sent back to the main screen between
    steps to work out what to click next."""
    app()
    unnamed = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    named_no_disk = replace(
        load_lsblk((FIXTURES / "lsblk_named.json").read_text()), backup_sets=[]
    )
    ready = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    stage = [named_no_disk]

    w = MainWindow(
        inventory=unnamed, last_run=None, reload_inventory=lambda: stage[0]
    )
    w.startButton.click()
    w.wizardIntroPage.startButton.click()
    assert w.stack.currentIndex() == PAGE_SETUP

    w.on_label_live_finished(0)
    assert w.stack.currentIndex() == PAGE_FORMAT
    assert w.formatPage.stepLabel.text() == "Step 2 of 3"

    stage[0] = ready
    w.on_format_finished(0)
    assert w.stack.currentIndex() == PAGE_WIZARD_FINISH
    assert w.wizardFinishPage.stepLabel.text() == "Step 3 of 3"
    assert "bak1" in w.wizardFinishPage.routeLabel.text()


def test_the_wizard_can_be_finished_without_backing_up():
    app()
    ready = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=ready, last_run=None, reload_inventory=lambda: ready)
    w.on_wizard_clicked()
    w.wizardIntroPage.startButton.click()
    assert w.stack.currentIndex() == PAGE_WIZARD_FINISH
    w.wizardFinishPage.laterButton.click()
    assert w.stack.currentIndex() == PAGE_HOME
    assert not w._wizard_active


def test_leaving_the_wizard_clears_the_step_counters():
    """Otherwise an expert opening the page directly sees a stale 'Step 2 of 3'."""
    app()
    unnamed = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    w = MainWindow(inventory=unnamed, last_run=None)
    w.startButton.click()
    w.wizardIntroPage.startButton.click()
    assert w.setupPage.stepLabel.text() == "Step 1 of 3"
    w.setupPage.leaveButton.click()
    assert w.stack.currentIndex() == PAGE_HOME
    assert w.setupPage.stepLabel.text() == ""
    assert w.setupPage.stepLabel.isHidden()


def test_an_unsupported_computer_is_never_walked_into_the_wizard():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_mbr_live.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.on_wizard_clicked()
    w.wizardIntroPage.startButton.click()
    assert w.stack.currentIndex() == PAGE_HOME


def test_a_long_path_does_not_widen_the_window():
    """Every deeper path made the window grow, and it never shrank back.

    A label reports the full width of its text as its preferred size, so the
    layout kept widening to fit paths that are wider than any screen.
    """
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    w.resize(720, 560)
    start = w.width()
    for depth in range(1, 40):
        w.show_current_file("home/alex/" + "a-quite-long-directory-name/" * depth + "f")
        w.layout().activate()
    assert w.sizeHint().width() <= start
    assert w.currentFileLabel.sizeHint().width() <= start


def test_the_first_path_cannot_widen_the_window_either():
    """Before the first layout pass there is no width to shorten the text to.

    Eliding is what keeps the label narrow once the window has been laid out,
    so the size policy is the only thing covering the very first path.
    """
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show_current_file("home/alex/" + "a-quite-long-directory-name/" * 40 + "f")
    assert (
        w.currentFileLabel.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    w.show()
    w.resize(720, 560)
    w.layout().activate()
    assert w.sizeHint().width() <= 720


def test_backup_progress_counts_partitions_not_flags():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _runnable_window(inv)
    w._run_backup_with_fselection("-bootfix,efi,root,home")
    assert not w.progressBar.isHidden()
    assert w.progressBar.maximum() == 3

    w._on_helper_line("START Directory SYNC FROM /boot/efi TO /mnt/bak1/efi")
    w._on_helper_line("EFI/ubuntu/grubx64.efi")
    w._on_helper_line("EFI/ubuntu/shimx64.efi")
    assert "Copying efi (1 of 3)" in w.progressBar.format()
    assert "2 files" in w.progressBar.format()

    w._on_helper_line("START Directory SYNC FROM / TO /mnt/bak1/root")
    assert "Copying root (2 of 3)" in w.progressBar.format()
    # The file count belongs to the partition being copied, not the whole run.
    assert "files" not in w.progressBar.format()
    assert w.progressBar.value() == 1


def test_a_failed_backup_does_not_leave_a_progress_bar_claiming_success():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _runnable_window(inv)
    w._run_backup_with_fselection("efi,root")
    w.on_helper_finished(1, "rsync failed")
    assert w.progressBar.isHidden()


def test_stopping_asks_first_and_goes_through_the_helper():
    """The GUI runs as the user and cannot signal root's rsync itself.

    Killing the pkexec child would leave the copying running with the window
    claiming it had stopped, so the request has to go back through the helper.
    """
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    sent = []
    w = _runnable_window(inv)
    w.ask_cancel = lambda: True
    w.start_cancel = sent.append
    w._run_backup_with_fselection("efi,root")
    assert not w.cancelButton.isHidden()
    w.cancelButton.click()
    assert len(sent) == 1
    assert sent[0][-1] == "cancel"
    assert not w.cancelButton.isEnabled()


def test_saying_let_it_finish_does_not_stop_anything():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    sent = []
    w = _runnable_window(inv)
    w.ask_cancel = lambda: False
    w.start_cancel = sent.append
    w._run_backup_with_fselection("efi,root")
    w.cancelButton.click()
    assert sent == []
    assert w.cancelButton.isEnabled()


def test_stopping_twice_only_asks_the_helper_once():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    sent = []
    w = _runnable_window(inv)
    w.ask_cancel = lambda: True
    w.start_cancel = sent.append
    w._run_backup_with_fselection("efi,root")
    w.on_cancel_clicked()
    w.on_cancel_clicked()
    assert len(sent) == 1


def test_a_stopped_backup_still_says_to_unplug_the_disk():
    """Stopping does not un-clone the UUIDs MBU has already written."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _runnable_window(inv)
    w.ask_cancel = lambda: True
    w.start_cancel = lambda argv: None
    w._run_backup_with_fselection("efi,root")
    w.cancelButton.click()
    w.on_helper_finished(143, "terminated")
    assert not w.unplugBanner.isHidden()
    assert w._backup_unfinished
    assert w.cancelButton.isHidden()


def test_error_and_unplug_and_busy():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show_error("The backup command failed (exit 1).")
    assert "exit 1" in w.logView.toPlainText()
    w.show_unplug(True)
    assert not w.unplugBanner.isHidden()
    w.set_running(True)
    assert not w.startButton.isEnabled()
    assert not w.setupButton.isEnabled()


def test_details_are_hidden_until_toggled():
    """The log used to eat the space the unplug banner needed on a small VM."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    assert w.logView.isHidden()
    assert w.detailsButton.text() == "See details"
    height_before = w.height()
    w.detailsButton.click()
    assert not w.logView.isHidden()
    assert w.detailsButton.text() == "Hide details"
    assert w.height() == height_before
    w.detailsButton.click()
    assert w.logView.isHidden()
    assert w.detailsButton.text() == "See details"


def test_details_toggle_still_works_off_home():
    """The log lives outside the page stack, so Prepare can still open it.

    Hidden-by-default is the product rule; the old test required the log to
    stay forced visible after leaving home.
    """
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    w.append_log("formatting...")
    w.formatButton.click()
    assert w.stack.currentIndex() == PAGE_FORMAT
    assert w.stack.indexOf(w.logView) == -1
    assert w.logView.isHidden()
    w.detailsButton.click()
    assert not w.logView.isHidden()
    assert "formatting..." in w.logView.toPlainText()
    w.show_unplug(True)
    assert not w.unplugBanner.isHidden()


def test_current_file_does_not_keep_a_cleanup_line_after_finish():
    """mbuclean's Status FINISHED sat in the current-file slot after a run."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _runnable_window(inv)
    w._run_backup_with_fselection("root")
    w._on_helper_line("home/alex/.bashrc")
    assert "bashrc" in w.currentFileLabel.text()
    w._on_helper_line(
        "mbuclean mbuClean:1269 Status FINISHED and removed /var/lib/mbu-gui/mount OK"
    )
    assert w.currentFileLabel.text() == ""
    w.on_helper_finished(0)
    assert w.currentFileLabel.text() == ""
    assert w.currentFileLabel.isHidden()


def test_displayed_log_strips_ansi_codes():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.append_log("\x1b[32mFINISHED\x1b[0m")
    w.append_log("[4m[1mDO NOT FORGET")
    text = w.logView.toPlainText()
    assert "FINISHED" in text
    assert "DO NOT FORGET" in text
    assert "[32m" not in text
    assert "[4m" not in text
    assert "[1m" not in text


def test_successful_backup_summarises_parsed_size_and_route():
    """'Backup finished' said nothing about how much went where."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _runnable_window(inv)
    w._run_backup_with_fselection("root")
    w._on_helper_line("BACKING UP PARTITION SET main TO bak1")
    w._on_helper_line("total size is 12,884,901,888  speedup is 1.00")
    w.on_helper_finished(0)
    assert w.cancelButton.isHidden()
    assert not w.summaryLabel.isHidden()
    assert (
        w.summaryLabel.text()
        == "Copied about 12 GB from this computer (main) onto bak1."
    )


def test_successful_backup_names_the_route_without_inventing_a_size():
    """rsync totals are missing on a quiet run; still say from-set → to-set."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _runnable_window(inv)
    w._run_backup_with_fselection("root")
    w.on_helper_finished(0)
    assert w.cancelButton.isHidden()
    assert not w.summaryLabel.isHidden()
    assert w.summaryLabel.text() == "Copied from this computer (main) onto bak1."
    assert "GB" not in w.summaryLabel.text()


def test_failed_backup_does_not_claim_a_successful_copy():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = _runnable_window(inv)
    w._run_backup_with_fselection("root")
    w._on_helper_line("total size is 12,884,901,888  speedup is 1.00")
    w.on_helper_finished(1, "rsync failed")
    assert w.summaryLabel.isHidden()
    assert "Copied" not in w.summaryLabel.text()


def test_window_fits_a_768_tall_desktop():
    """resize(720, 560) ignored the taskbar, so the unplug banner was clipped."""
    width, height = window_size_for_screen(1024, 768)
    assert height <= 768
    assert width <= 1024
    _, short = window_size_for_screen(1366, 700)
    assert short <= 700
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    assert w.sizeHint().height() <= 768


def test_icon_candidates_include_installed_and_repo_paths():
    paths = [str(p) for p in _icon_candidates()]
    assert "/usr/share/mbu-gui/mbu-icon.png" in paths
    assert any(p.endswith("/data/mbu-icon.png") for p in paths)


def test_close_ignored_while_running():
    """The red X used to do nothing at all, with no hint why."""
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None, ask_cancel=lambda: False)
    w.show()
    w.set_running(True)
    event = QCloseEvent()
    w.closeEvent(event)
    assert not event.isAccepted()
    assert w.isVisible()
    assert "would not stop it" in w.logView.toPlainText()


def test_close_refused_while_browse_mounted():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    w = MainWindow(inventory=inv, last_run=None)
    w.show()
    w.browsePage.set_mounted(True)
    event = QCloseEvent()
    w.closeEvent(event)
    assert not event.isAccepted()
    assert "Unmount" in w.logView.toPlainText()


def test_refresh_after_backup_and_when_returning_home():
    app()
    inv = load_lsblk((FIXTURES / "lsblk_named.json").read_text())
    unnamed = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    last = LastRun(
        timestamp="2026/08/31-12:00:00",
        from_set="main",
        to_set="bak1",
        functions="root",
        ok=True,
    )
    counts = {"inv": 0, "last": 0}

    def reload_inventory():
        counts["inv"] += 1
        return unnamed if counts["inv"] == 1 else inv

    def reload_last_run():
        counts["last"] += 1
        return last

    w = MainWindow(
        inventory=inv,
        last_run=None,
        helper_exists=True,
        pkexec_exists=True,
        start_process=lambda argv: None,
        helper_path=Path("/usr/lib/mbu-gui/mbu-gui-helper"),
        reload_inventory=reload_inventory,
        reload_last_run=reload_last_run,
    )
    w._run_backup_with_fselection("root")
    w.on_helper_finished(0)
    assert counts["inv"] >= 1
    assert counts["last"] >= 1
    assert "2026/08/31-12:00:00" in w.lastRunLabel.text()
    assert w.statusLabel.text() == unnamed.status_line

    before = dict(counts)
    w.setupButton.click()
    assert w.stack.currentIndex() == PAGE_SETUP
    w.setupPage.leaveButton.click()
    assert w.stack.currentIndex() == PAGE_HOME
    assert counts["inv"] > before["inv"]
    assert counts["last"] > before["last"]
    assert w._refresh_timer.interval() == 2000
