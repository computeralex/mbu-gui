from dataclasses import replace
from pathlib import Path

from mbu_gui.disks import load_lsblk
from mbu_gui.wizard import (
    INTRO_TEXT,
    STEP_BACKUP,
    STEP_BLOCKED,
    STEP_FORMAT,
    STEP_SETUP,
    completed_steps,
    current_step,
    resume_note,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _inv(name):
    return load_lsblk((FIXTURES / name).read_text())


def test_an_unnamed_computer_starts_at_the_first_step():
    step = current_step(_inv("lsblk_unnamed.json"))
    assert step.name == STEP_SETUP
    assert step.counter == "Step 1 of 3"


def test_a_named_computer_without_a_disk_resumes_at_preparing_one():
    """Reopening the app must not replay steps that are already done."""
    inv = replace(_inv("lsblk_named.json"), backup_sets=[])
    step = current_step(inv)
    assert step.name == STEP_FORMAT
    assert step.counter == "Step 2 of 3"
    assert completed_steps(inv) == [STEP_SETUP]
    assert "already named" in resume_note(inv)


def test_a_ready_computer_resumes_at_the_backup():
    inv = _inv("lsblk_named.json")
    step = current_step(inv)
    assert step.name == STEP_BACKUP
    assert step.counter == "Step 3 of 3"
    assert "only the backup itself is left" in resume_note(inv)


def test_the_counter_does_not_renumber_as_steps_are_skipped():
    """Step 3 stays step 3, so a resumed run does not look like a new one."""
    unnamed = current_step(_inv("lsblk_unnamed.json"))
    ready = current_step(_inv("lsblk_named.json"))
    assert (unnamed.number, unnamed.total) == (1, 3)
    assert (ready.number, ready.total) == (3, 3)


def test_a_computer_awaiting_a_restart_is_not_walked_through_setup_again():
    inv = replace(_inv("lsblk_unnamed.json"), awaiting_restart=True)
    assert current_step(inv).name == STEP_BLOCKED


def test_an_unsupported_computer_never_enters_the_wizard():
    step = current_step(_inv("lsblk_mbr_live.json"))
    assert step.name == STEP_BLOCKED
    assert "MBR" in step.detail


def test_the_clone_guard_is_not_a_step_the_wizard_can_walk_past():
    inv = replace(
        _inv("lsblk_named.json"),
        start_blocked_reason="This computer is recorded as set `main`",
    )
    assert current_step(inv).name == STEP_BLOCKED


def test_the_intro_says_deletions_are_mirrored():
    """The gap that costs people data: 'backup' does not mean 'file history'."""
    assert "deleted from" in INTRO_TEXT
    assert "not a file archive" in INTRO_TEXT
    assert "boot" in INTRO_TEXT


def test_nothing_is_reported_done_before_anything_has_been_done():
    assert completed_steps(_inv("lsblk_unnamed.json")) == []
    assert resume_note(_inv("lsblk_unnamed.json")) == ""
