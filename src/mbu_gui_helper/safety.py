from __future__ import annotations

from mbu_gui.disks import Inventory, Partition, disks_with_id

live_disk_error = "Refusing to format or wipe the disk that contains /"
label_wrong_disk_error = "Refusing to label a partition that is not on the disk that contains /"
missing_disk_id_error = (
    "Refusing to format a disk that reports no serial number or hardware id."
)
unknown_disk_id_error = (
    "Refusing to format: no attached disk has that hardware id any more. "
    "Go back, pick the disk again, and retry."
)
ambiguous_disk_id_error = (
    "Refusing to format: two attached disks report the same hardware id."
)
renamed_disk_error = (
    "Refusing to format: that disk changed device name since you picked it. "
    "Go back, pick the disk again, and retry."
)


def normalize_disk(name: str) -> str:
    if name.startswith("/dev/"):
        return name[len("/dev/") :]
    return name


def assert_not_live_disk(disk: str, inventory: Inventory) -> None:
    if inventory.live_disk is None or normalize_disk(disk) == inventory.live_disk:
        raise ValueError(live_disk_error)


def resolve_format_target(disk_id: str, expected_name: str, inventory: Inventory) -> str:
    """Resolve the disk to erase from its hardware id, against a fresh inventory.

    The GUI captured disk_id when it drew the list; we re-resolve it here so a
    replug that renamed the device cannot redirect the wipe. Any disagreement
    with the name the GUI expected aborts instead of guessing.
    """
    if not disk_id.strip():
        raise ValueError(missing_disk_id_error)
    matches = disks_with_id(inventory, disk_id)
    if not matches:
        raise ValueError(unknown_disk_id_error)
    if len(matches) > 1:
        raise ValueError(ambiguous_disk_id_error)
    disk = matches[0]
    if disk.name != normalize_disk(expected_name):
        raise ValueError(renamed_disk_error)
    return disk.name


def assert_label_targets_live(part_name: str, inventory: Inventory) -> Partition:
    for disk in inventory.disks:
        for part in disk.partitions:
            if part.name == part_name:
                if part.disk != inventory.live_disk:
                    raise ValueError(label_wrong_disk_error)
                return part
    raise ValueError(f"Unknown partition: {part_name}")
