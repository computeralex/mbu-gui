"""Record of which MBU partition set is *this* computer.

MBU decides what to copy from by looking at whatever partition is mounted at
/ right now. After a UUID clone, leaving the backup disk plugged in and
rebooting can land Linux on the clone. Everything then looks normal, except
the roles are swapped: the clone becomes the source and the real system disk
looks like a backup, so the next backup writes the clone over the internal
disk.

Deriving the answer from the running system at backup time cannot detect
that, so the machine's own set name is written down once and checked
afterwards. The record lives inside the root filesystem, so a clone carries a
copy naming the original set, which is exactly what makes the mismatch
visible from the clone.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import json

from mbu_gui.disks import Inventory

MACHINE_RECORD_NAME = "machine.json"

CLONE_STATUS_LINE = "Running from the wrong disk"

corrupt_record_error = (
    "Cannot read which computer this is (machine.json is unreadable). "
    "Refusing to back up until that is fixed."
)


@dataclass(frozen=True)
class MachineRecord:
    machine_set: str
    disk_id: str | None = None


def record_path(state_dir: Path) -> Path:
    return state_dir / MACHINE_RECORD_NAME


def load_machine_record(path: Path) -> MachineRecord | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        machine_set = data["machine_set"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(corrupt_record_error) from e
    if not isinstance(machine_set, str) or not machine_set:
        raise ValueError(corrupt_record_error)
    disk_id = data.get("disk_id")
    return MachineRecord(
        machine_set=machine_set,
        disk_id=disk_id if isinstance(disk_id, str) else None,
    )


def save_machine_record(path: Path, record: MachineRecord) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"Refusing to write machine record through {path}")
    path.write_text(
        json.dumps({"machine_set": record.machine_set, "disk_id": record.disk_id}) + "\n"
    )


def live_disk_id(inventory: Inventory) -> str | None:
    for disk in inventory.disks:
        if disk.name == inventory.live_disk:
            return disk.disk_id
    return None


def record_for(inventory: Inventory) -> MachineRecord | None:
    if inventory.live_set is None:
        return None
    return MachineRecord(machine_set=inventory.live_set, disk_id=live_disk_id(inventory))


def inversion_reason(record: MachineRecord | None, inventory: Inventory) -> str | None:
    """Explain why this system looks like it booted from a backup, if it does."""
    if record is None or inventory.live_set is None:
        return None
    if inventory.live_set == record.machine_set:
        return None
    return (
        f"This computer is recorded as set `{record.machine_set}`, but right now "
        f"it is running from set `{inventory.live_set}`. That usually means Linux "
        "booted from the backup disk instead of the internal disk. Backing up now "
        "would copy the backup over your real system disk. Shut down, unplug the "
        "backup disk, then start the computer again."
    )


def apply_machine_guard(inventory: Inventory, record: MachineRecord | None) -> Inventory:
    reason = inversion_reason(record, inventory)
    if reason is None:
        return inventory
    return replace(inventory, start_blocked_reason=reason, status_line=CLONE_STATUS_LINE)
