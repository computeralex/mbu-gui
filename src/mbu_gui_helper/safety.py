from __future__ import annotations

from mbu_gui.disks import (
    Inventory,
    Partition,
    disks_with_id,
    live_disk_unsupported,
)

live_disk_error = "Refusing to format or wipe the disk that contains /"
system_disk_error = (
    "Refusing to format or wipe a disk the running system is using "
    "(it holds a mounted filesystem or active swap)"
)
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


def assert_not_system_disk(disk: str, inventory: Inventory) -> None:
    """Refuse any disk the running system depends on, not only the one with /.

    Fails closed when / cannot be located at all: if we cannot tell what the
    system is using, we must not erase anything.
    """
    name = normalize_disk(disk)
    if inventory.live_disk is None or name == inventory.live_disk:
        raise ValueError(live_disk_error)
    if name in inventory.system_disks:
        raise ValueError(system_disk_error)


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


def assert_live_disk_supports_names(inventory: Inventory) -> None:
    """Refuse to write partition names a table cannot store.

    On an MBR disk sfdisk reports success, rewrites the table and drops the
    name, so the GUI keeps asking the user to set up the computer forever.
    Failing loudly here beats rewriting the live partition table to no effect.
    """
    unsupported = live_disk_unsupported(inventory)
    if unsupported is not None:
        raise ValueError(unsupported)


def assert_label_targets_live(part_name: str, inventory: Inventory) -> Partition:
    for disk in inventory.disks:
        for part in disk.partitions:
            if part.name == part_name:
                if part.disk != inventory.live_disk:
                    raise ValueError(label_wrong_disk_error)
                return part
    raise ValueError(f"Unknown partition: {part_name}")
