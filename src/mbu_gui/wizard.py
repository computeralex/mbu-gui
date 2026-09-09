"""Which step of the guided setup a computer is actually on.

Deliberately derived from the current inventory rather than remembered. A
wizard that stores "the user is on step 3" goes wrong the moment anything
happens outside it: a disk is unplugged, the app is closed, the machine is
rebooted between steps. Asking the disks every time cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass

from mbu_gui.disks import (
    Inventory,
    describe_backup_route,
    live_disk_unsupported,
)

WIZARD_BUTTON_TEXT = "Take me through it"

INTRO_TITLE = "What MBU Backup does"
# The single most misunderstood thing about this product. People hear "backup"
# and assume they can get back a file they deleted last week. They cannot, and
# finding that out during a real emergency is the worst possible time.
INTRO_TEXT = (
    "MBU makes a complete copy of this computer onto a spare disk, and that "
    "copy can boot. If this computer's disk dies, you start the backup disk "
    "instead and carry on working.\n\n"
    "It is a mirror, not a file archive. Each backup makes the spare disk "
    "match this computer exactly, so anything you delete here is deleted from "
    "the backup on the next run. It protects you from a dead disk or a stolen "
    "computer. It does not let you recover last week's version of a file.\n\n"
    "This will take you through the three steps: naming this computer, "
    "preparing a spare disk, and making the first backup."
)

STEP_SETUP = "setup"
STEP_FORMAT = "format"
STEP_BACKUP = "backup"
STEP_DONE = "done"
STEP_BLOCKED = "blocked"

_TITLES = {
    STEP_SETUP: "Name this computer",
    STEP_FORMAT: "Prepare a backup disk",
    STEP_BACKUP: "Make the first backup",
}
# Every run passes through these, whether or not a given one needs doing, so
# the counter does not renumber itself as the user progresses.
_ORDER = (STEP_SETUP, STEP_FORMAT, STEP_BACKUP)


@dataclass(frozen=True)
class WizardStep:
    name: str
    title: str
    number: int
    total: int
    detail: str = ""

    @property
    def counter(self) -> str:
        if self.number <= 0:
            return ""
        return f"Step {self.number} of {self.total}"


def _step(name: str, detail: str = "") -> WizardStep:
    total = len(_ORDER)
    if name not in _ORDER:
        return WizardStep(name, _TITLES.get(name, ""), 0, total, detail)
    return WizardStep(name, _TITLES[name], _ORDER.index(name) + 1, total, detail)


def current_step(inventory: Inventory) -> WizardStep:
    """The first step that still needs doing, or done."""
    unsupported = live_disk_unsupported(inventory)
    if unsupported is not None:
        return _step(STEP_BLOCKED, unsupported)
    if inventory.awaiting_restart:
        return _step(STEP_BLOCKED, "")
    if inventory.unnamed_live:
        return _step(STEP_SETUP)
    if not inventory.backup_sets:
        return _step(STEP_FORMAT)
    if inventory.start_blocked_reason is not None:
        return _step(STEP_BLOCKED, inventory.start_blocked_reason)
    if describe_backup_route(inventory) is None:
        return _step(STEP_BLOCKED, "Cannot tell which disk would be written to.")
    return _step(STEP_BACKUP)


def completed_steps(inventory: Inventory) -> list[str]:
    """Steps already satisfied, so the wizard can say what it is skipping."""
    done = []
    if not inventory.unnamed_live and live_disk_unsupported(inventory) is None:
        done.append(STEP_SETUP)
    if inventory.backup_sets:
        done.append(STEP_FORMAT)
    return done


def resume_note(inventory: Inventory) -> str:
    """One line telling a returning user what is already out of the way."""
    done = completed_steps(inventory)
    if not done:
        return ""
    if len(done) == len(_ORDER) - 1:
        return (
            "This computer is named and a backup disk is ready, so only the "
            "backup itself is left."
        )
    if STEP_SETUP in done:
        return "This computer is already named, so that step is done."
    return "A backup disk is already prepared, so that step is done."
