from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
import json
import re
from typing import Any


_SET_NAME_RE = re.compile(r"^[A-Za-z0-9]+$")
_NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]")

CONFIRM_TOKEN_LEN = 8

NO_DISK_ID_TEXT = (
    "This disk reports no serial number, so MBU cannot tell it apart from "
    "another disk after a replug. Refusing to format it."
)

SWAP_MOUNTPOINT = "[SWAP]"
# Anything mounted outside these trees counts as the running system using the
# disk. Removable-media mounts are where the desktop auto-mounts a USB stick,
# which is exactly the disk the user wants to prepare as a backup.
_REMOVABLE_MOUNT_DIRS = ("/media", "/run/media", "/mnt")

_MOUNT_FUNCTIONS = {
    "/": "root",
    "/home": "home",
    "/boot": "boot",
    "/boot/efi": "efi",
    "/tmp": "tmp",
}

GPT_PTTYPE = "gpt"

_MBR_LIVE_REASON = (
    "This computer's disk uses an old MBR partition table, and MBU needs GPT "
    "with an EFI partition. That normally means Linux was installed in legacy "
    "BIOS mode rather than UEFI mode.\n\n"
    "Nothing in this app can change that. Reinstalling Linux in UEFI mode is "
    "the only way to make this computer work with MBU."
)
_MBR_STATUS = "This disk uses MBR, which MBU cannot use"

_UNNAMED_LIVE_REASON = (
    "This computer's partitions are not named for MBU yet. Use Set up this computer."
)
_NO_BACKUP_REASON = "Plug in the backup disk"
_MULTIPLE_BACKUP_REASON = (
    "Several backup disks are connected. Unplug the extras so only the one you want to update is attached."
)
_MULTIPLE_BACKUP_STATUS = "Several backup disks are connected"


@dataclass(frozen=True)
class Partition:
    name: str
    path: str
    disk: str
    partn: int | None
    size: str
    fstype: str | None
    mountpoint: str | None
    partlabel: str | None
    uuid: str | None


@dataclass(frozen=True)
class Disk:
    name: str
    path: str
    size: str
    model: str | None
    partitions: list[Partition]
    serial: str | None = None
    wwn: str | None = None
    ptuuid: str | None = None
    pttype: str | None = None

    @property
    def disk_id(self) -> str | None:
        """Persistent hardware id, or None when the disk reports nothing stable.

        Kernel names like sdb are reassigned on replug, so they must never be
        the only thing identifying a disk we are about to erase.
        """
        for prefix, value in (("wwn", self.wwn), ("serial", self.serial), ("ptuuid", self.ptuuid)):
            cleaned = (value or "").strip()
            if cleaned:
                return f"{prefix}:{cleaned.lower()}"
        return None


@dataclass(frozen=True)
class Inventory:
    disks: list[Disk]
    live_disk: str | None
    live_set: str | None
    backup_sets: list[str]
    live_functions: list[str]
    unnamed_live: bool
    multiple_backup_sets: bool
    status_line: str
    start_blocked_reason: str | None
    system_disks: list[str] = field(default_factory=list)
    live_pttype: str | None = None

    @classmethod
    def empty(cls, reason: str) -> Inventory:
        return cls(
            disks=[],
            live_disk=None,
            live_set=None,
            backup_sets=[],
            live_functions=[],
            unnamed_live=True,
            multiple_backup_sets=False,
            status_line="Could not read disks",
            start_blocked_reason=reason,
            system_disks=[],
            live_pttype=None,
        )


def is_valid_set_name(name: str) -> bool:
    return _SET_NAME_RE.fullmatch(name) is not None


def split_mbu_label(label: str | None) -> tuple[str, str] | None:
    if label is None or "-" not in label:
        return None
    set_name, function = label.split("-", 1)
    if not is_valid_set_name(set_name) or not is_valid_set_name(function):
        return None
    return (set_name, function)


def propose_function(part: Partition) -> str:
    mount = part.mountpoint
    if mount in _MOUNT_FUNCTIONS:
        return _MOUNT_FUNCTIONS[mount]
    if part.fstype == "swap":
        return "swap"
    if part.fstype == "vfat" and not mount:
        return "efi"
    if mount:
        stripped = _NON_ALNUM_RE.sub("", mount.rsplit("/", 1)[-1])
        if stripped:
            return stripped
    suffix = "" if part.partn is None else str(part.partn)
    return f"part{suffix}"


def propose_labels(inventory: Inventory, set_name: str) -> list[tuple[Partition, str]]:
    labels: list[tuple[Partition, str]] = []
    for disk in inventory.disks:
        if disk.name != inventory.live_disk:
            continue
        for part in disk.partitions:
            labels.append((part, f"{set_name}-{propose_function(part)}"))
    return labels


def candidate_backup_disks(inventory: Inventory) -> list[Disk]:
    if inventory.live_disk is None:
        return []
    excluded = {inventory.live_disk, *inventory.system_disks}
    return [disk for disk in inventory.disks if disk.name not in excluded]


def destination_disks(inventory: Inventory, set_name: str) -> list[Disk]:
    found: list[Disk] = []
    for disk in inventory.disks:
        for part in disk.partitions:
            parsed = split_mbu_label(part.partlabel)
            if parsed is not None and parsed[0] == set_name:
                found.append(disk)
                break
    return found


def describe_disk(disk: Disk) -> str:
    bits = [disk.name, disk.size, disk.model or "", disk.disk_id or "no serial reported"]
    return "  ".join(b for b in bits if b)


def describe_backup_route(inventory: Inventory) -> str | None:
    """Which disk a backup would overwrite, for the confirmation dialog.

    Returns None when that cannot be stated unambiguously, so the caller can
    refuse to start rather than let the user confirm an unnamed destination.
    """
    if inventory.live_set is None or len(inventory.backup_sets) != 1:
        return None
    set_name = inventory.backup_sets[0]
    disks = destination_disks(inventory, set_name)
    if not disks:
        return None
    targets = "\n".join(f"    {describe_disk(disk)}" for disk in disks)
    return (
        f"From this computer (set `{inventory.live_set}`)\n"
        f"Onto backup set `{set_name}`, overwriting:\n{targets}"
    )


def find_disk(inventory: Inventory, name: str | None) -> Disk | None:
    for disk in inventory.disks:
        if disk.name == name:
            return disk
    return None


def disk_set_names(disk: Disk) -> set[str]:
    """MBU set names currently written on this disk's partitions."""
    names: set[str] = set()
    for part in disk.partitions:
        parsed = split_mbu_label(part.partlabel)
        if parsed is not None:
            names.add(parsed[0])
    return names


def other_disk_set_names(inventory: Inventory, disk: Disk) -> set[str]:
    """Set names in use on every disk except this one.

    A name already on the disk we are about to erase is not a conflict: that
    label is about to be overwritten. Re-preparing a backup disk under its
    existing name is the common case, so only names on *other* attached disks
    can collide.
    """
    names: set[str] = set()
    for other in inventory.disks:
        if other.name == disk.name:
            continue
        names |= disk_set_names(other)
    return names


def suggested_set_name(inventory: Inventory, disk: Disk) -> str:
    """A set name that will pass validation, so the field is never dead on arrival."""
    taken = other_disk_set_names(inventory, disk)
    if inventory.live_set:
        taken.add(inventory.live_set)
    existing = sorted(disk_set_names(disk))
    for name in existing:
        if name not in taken:
            return name
    for n in range(1, 100):
        candidate = "backup" if n == 1 else f"backup{n}"
        if candidate not in taken:
            return candidate
    return ""


def setup_block_reason(
    inventory: Inventory,
    name: str,
    typed_confirm: str,
) -> str | None:
    """Why Set up this computer cannot proceed yet.

    Same failure as the prepare page: several conditions gate Apply names and
    none were shown, so the default name on an already-named machine produced a
    dead button with no explanation.
    """
    unsupported = live_disk_unsupported(inventory)
    if unsupported is not None:
        return unsupported
    if not name:
        return "Give this computer's partitions a set name."
    if not is_valid_set_name(name):
        return f"`{name}` will not work as a set name. Use letters and digits only."
    if name == inventory.live_set:
        return (
            f"This computer's partitions are already named `{name}`. "
            "You can leave them alone."
        )
    if name in inventory.backup_sets:
        return (
            f"`{name}` is already used by a backup disk that is plugged in. "
            "Pick a different name."
        )
    if typed_confirm != name:
        return f"Type {name} in the box above to confirm."
    return None


def format_block_reason(
    inventory: Inventory,
    disk: Disk | None,
    pset: str,
    typed_confirm: str,
) -> str | None:
    """Why Prepare a backup disk cannot proceed yet, in the user's words.

    Five separate conditions gate the wipe and none of them used to be shown,
    so an unmet one produced a dead button and no way to find out which.
    """
    if disk is None:
        return "Choose which disk to prepare from the list above."
    if disk.disk_id is None:
        return NO_DISK_ID_TEXT
    if not pset:
        return "Give this backup set a name. Any letters and digits will do."
    if not is_valid_set_name(pset):
        return f"`{pset}` will not work as a set name. Use letters and digits only."
    if pset == inventory.live_set:
        return (
            f"`{pset}` is this computer's own set name. "
            "Give the backup disk a different name."
        )
    if pset in other_disk_set_names(inventory, disk):
        return (
            f"`{pset}` is already used by another disk that is plugged in. "
            "Pick a different name or unplug that disk."
        )
    token = confirm_token(disk)
    if token is None:
        return NO_DISK_ID_TEXT
    if typed_confirm.strip().lower() != token:
        return (
            f"Type the code {token.upper()} in the box above to confirm that "
            f"{disk.name} is the disk you want to erase."
        )
    return None


@dataclass(frozen=True)
class NextStep:
    """The one thing the user should do next, and why.

    The home screen used to show a disabled Start Backup plus a separate
    sentence explaining the block, which is easy to miss: the user sees a dead
    button and concludes the app is broken. Instead the primary button always
    offers the next action that actually moves them forward.
    """

    action: str
    label: str
    detail: str
    enabled: bool = True
    # Short line shown in place of the primary button when no action exists.
    headline: str = ""


_SETUP_DETAIL = (
    "First this computer's partitions need MBU names. This only names them; "
    "nothing is erased."
)
_FORMAT_DETAIL = (
    "No backup disk is connected. Plug in the disk you already prepared, or "
    "prepare a new one. If you just prepared a disk, plug it back in and this "
    "will change to Back up now."
)


def next_step(inventory: Inventory) -> NextStep:
    unsupported = live_disk_unsupported(inventory)
    if unsupported is not None:
        # No action exists, so the caller hides the button rather than offering
        # a dead one. A greyed-out "Back up now" reads as the app suggesting
        # the single thing it can never do here.
        return NextStep(
            "blocked",
            "Cannot back up this computer",
            unsupported,
            enabled=False,
            headline="This computer cannot be backed up",
        )
    if inventory.unnamed_live:
        return NextStep("setup", "Set up this computer", _SETUP_DETAIL)
    if not inventory.backup_sets:
        return NextStep("format", "Prepare a backup disk", _FORMAT_DETAIL)
    if len(inventory.backup_sets) > 1:
        return NextStep(
            "blocked",
            "Unplug the extra backup disks",
            _MULTIPLE_BACKUP_REASON,
            enabled=False,
            headline="Too many backup disks are connected",
        )
    if inventory.start_blocked_reason is not None:
        # Something outside the disk layout is blocking, such as the guard that
        # fires when we booted from a clone. Never offer a way past that.
        return NextStep(
            "blocked",
            "Cannot back up right now",
            inventory.start_blocked_reason,
            enabled=False,
            headline="Backing up is not safe right now",
        )
    route = describe_backup_route(inventory)
    if route is None:
        return NextStep(
            "blocked",
            "Cannot back up right now",
            "Cannot tell which disk would be written to.",
            enabled=False,
            headline="The backup disk cannot be identified",
        )
    return NextStep("backup", "Back up now", route)


def disks_with_id(inventory: Inventory, disk_id: str) -> list[Disk]:
    wanted = disk_id.strip().lower()
    if not wanted:
        return []
    return [disk for disk in inventory.disks if disk.disk_id == wanted]


def confirm_token(disk: Disk) -> str | None:
    """Short code the user types to confirm a wipe, derived from the hardware id.

    Only an attention gate: the disk we erase is the one whose disk_id we
    captured from the selected row, never the one whose token was typed.
    """
    disk_id = disk.disk_id
    if disk_id is None:
        return None
    return disk_id.split(":", 1)[1][-CONFIRM_TOKEN_LEN:]


def load_lsblk(text: str) -> Inventory:
    return parse_lsblk(json.loads(text))


def parse_lsblk(data: dict[str, Any]) -> Inventory:
    blockdevices = data.get("blockdevices") or []
    disks = _disks_from_blockdevices(blockdevices)
    live_disk = _live_disk_name(blockdevices)
    live_part = _live_partition(disks, live_disk, blockdevices)
    live_parsed = split_mbu_label(live_part.partlabel) if live_part is not None else None
    live_set = live_parsed[0] if live_parsed is not None else None
    unnamed_live = live_parsed is None
    live_functions = _live_functions(disks, live_disk, live_set)
    backup_sets = _backup_sets(disks, live_set)
    multiple_backup_sets = len(backup_sets) > 1
    live_pttype = _live_pttype(disks, live_disk)
    return Inventory(
        disks=disks,
        live_disk=live_disk,
        live_set=live_set,
        backup_sets=backup_sets,
        live_functions=live_functions,
        unnamed_live=unnamed_live,
        multiple_backup_sets=multiple_backup_sets,
        status_line=_status_line(backup_sets, live_pttype),
        start_blocked_reason=_start_blocked_reason(
            unnamed_live, backup_sets, live_pttype
        ),
        system_disks=_system_disk_names(blockdevices),
        live_pttype=live_pttype,
    )


def _disks_from_blockdevices(blockdevices: list[dict[str, Any]]) -> list[Disk]:
    disks: list[Disk] = []
    for dev in blockdevices:
        if dev.get("type") != "disk":
            continue
        name = dev["name"]
        disks.append(
            Disk(
                name=name,
                path=dev.get("path") or f"/dev/{name}",
                size=dev.get("size") or "",
                model=dev.get("model"),
                partitions=_partitions_for_disk(dev, name),
                serial=dev.get("serial"),
                wwn=dev.get("wwn"),
                ptuuid=dev.get("ptuuid"),
                pttype=dev.get("pttype"),
            )
        )
    return disks


def _partitions_for_disk(dev: dict[str, Any], disk_name: str) -> list[Partition]:
    parts: list[Partition] = []
    for child in dev.get("children") or []:
        for node in _walk(child):
            if node.get("type") == "part":
                parts.append(_partition_from_node(node, disk_name))
    return parts


def _walk(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


def _partition_from_node(node: dict[str, Any], disk_name: str) -> Partition:
    name = node["name"]
    return Partition(
        name=name,
        path=node.get("path") or f"/dev/{name}",
        disk=disk_name,
        partn=node.get("partn"),
        size=node.get("size") or "",
        fstype=node.get("fstype"),
        mountpoint=node.get("mountpoint"),
        partlabel=node.get("partlabel"),
        uuid=node.get("uuid"),
    )


def _node_mountpoints(node: dict[str, Any]) -> list[str]:
    """Every mountpoint of one node, from both lsblk spellings.

    MOUNTPOINT reports only the first mount, which hides the rest on layouts
    like btrfs subvolumes where one device carries / and /home at once.
    """
    found = [node.get("mountpoint")]
    found.extend(node.get("mountpoints") or [])
    return [m for m in found if m]


def _has_mountpoint(node: dict[str, Any], mount: str) -> bool:
    if mount in _node_mountpoints(node):
        return True
    for child in node.get("children") or []:
        if _has_mountpoint(child, mount):
            return True
    return False


def _is_system_mountpoint(mountpoint: str) -> bool:
    if mountpoint == SWAP_MOUNTPOINT:
        return True
    if not mountpoint.startswith("/"):
        return False
    if mountpoint in _REMOVABLE_MOUNT_DIRS:
        return False
    return not mountpoint.startswith(tuple(d + "/" for d in _REMOVABLE_MOUNT_DIRS))


def _system_disk_names(blockdevices: list[dict[str, Any]]) -> list[str]:
    """Disks the running system is using, not just the one holding /.

    A separate /boot/efi disk, a separate /home disk, an active swap disk and
    every member of a multi-disk LVM or RAID root all belong here: erasing any
    of them breaks the running system. lsblk repeats a spanning LV under each
    of its physical disks, so walking each disk's own subtree finds them all.
    """
    names: list[str] = []
    for dev in blockdevices:
        if dev.get("type") != "disk":
            continue
        for node in _walk(dev):
            if any(_is_system_mountpoint(m) for m in _node_mountpoints(node)):
                names.append(dev["name"])
                break
    return names


def _live_disk_name(blockdevices: list[dict[str, Any]]) -> str | None:
    for dev in blockdevices:
        if dev.get("type") != "disk":
            continue
        if _has_mountpoint(dev, "/"):
            return dev["name"]
    return None


def _live_partition(
    disks: list[Disk],
    live_disk: str | None,
    blockdevices: list[dict[str, Any]],
) -> Partition | None:
    if live_disk is None:
        return None
    part_name = None
    for dev in blockdevices:
        if dev.get("type") != "disk" or dev.get("name") != live_disk:
            continue
        for node in _walk(dev):
            if node.get("type") == "part" and _has_mountpoint(node, "/"):
                part_name = node.get("name")
                break
    for disk in disks:
        if disk.name != live_disk:
            continue
        for part in disk.partitions:
            if part_name is not None and part.name == part_name:
                return part
            if part.mountpoint == "/":
                return part
    return None


def _live_functions(disks: list[Disk], live_disk: str | None, live_set: str | None) -> list[str]:
    if live_disk is None or live_set is None:
        return []
    functions: list[str] = []
    for disk in disks:
        if disk.name != live_disk:
            continue
        for part in disk.partitions:
            parsed = split_mbu_label(part.partlabel)
            if parsed is not None and parsed[0] == live_set:
                functions.append(parsed[1])
    return functions


def _backup_sets(disks: list[Disk], live_set: str | None) -> list[str]:
    names: set[str] = set()
    for disk in disks:
        for part in disk.partitions:
            parsed = split_mbu_label(part.partlabel)
            if parsed is not None and parsed[0] != live_set:
                names.add(parsed[0])
    return sorted(names)


def _live_pttype(disks: list[Disk], live_disk: str | None) -> str | None:
    for disk in disks:
        if disk.name == live_disk:
            return (disk.pttype or "").lower() or None
    return None


def live_disk_unsupported(inventory: Inventory) -> str | None:
    """Why this computer cannot be backed up at all, if it cannot.

    An MBR disk has no place to store a partition name, so labelling appears to
    succeed and then vanishes. Detecting it here turns a silent loop through
    Set up this computer into one sentence explaining that the disk is wrong.
    """
    pttype = inventory.live_pttype
    if pttype is None or pttype == GPT_PTTYPE:
        return None
    return _MBR_LIVE_REASON


def _status_line(backup_sets: list[str], live_pttype: str | None = None) -> str:
    if live_pttype is not None and live_pttype != GPT_PTTYPE:
        return _MBR_STATUS
    if not backup_sets:
        return _NO_BACKUP_REASON
    if len(backup_sets) > 1:
        return _MULTIPLE_BACKUP_STATUS
    return f"Backup disk `{backup_sets[0]}` is connected"


def _start_blocked_reason(
    unnamed_live: bool,
    backup_sets: list[str],
    live_pttype: str | None = None,
) -> str | None:
    # Checked before the unnamed case: an MBR disk always looks unnamed, and
    # sending the user to Set up this computer is exactly the dead end.
    if live_pttype is not None and live_pttype != GPT_PTTYPE:
        return _MBR_LIVE_REASON
    if unnamed_live:
        return _UNNAMED_LIVE_REASON
    if not backup_sets:
        return _NO_BACKUP_REASON
    if len(backup_sets) > 1:
        return _MULTIPLE_BACKUP_REASON
    return None
