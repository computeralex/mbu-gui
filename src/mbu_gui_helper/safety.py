from __future__ import annotations

from mbu_gui.disks import Inventory, Partition

live_disk_error = "Refusing to format or wipe the disk that contains /"
label_wrong_disk_error = "Refusing to label a partition that is not on the disk that contains /"


def normalize_disk(name: str) -> str:
    if name.startswith("/dev/"):
        return name[len("/dev/") :]
    return name


def assert_not_live_disk(disk: str, inventory: Inventory) -> None:
    if normalize_disk(disk) == inventory.live_disk:
        raise ValueError(live_disk_error)


def assert_label_targets_live(part_name: str, inventory: Inventory) -> Partition:
    for disk in inventory.disks:
        for part in disk.partitions:
            if part.name == part_name:
                if part.disk != inventory.live_disk:
                    raise ValueError(label_wrong_disk_error)
                return part
    raise ValueError(f"Unknown partition: {part_name}")
