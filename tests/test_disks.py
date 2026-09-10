# tests/test_disks.py
from dataclasses import replace
from pathlib import Path

from mbu_gui.disks import (
    Inventory,
    candidate_backup_disks,
    confirm_token,
    disks_with_id,
    is_valid_set_name,
    load_lsblk,
    parse_lsblk,
    propose_function,
    propose_labels,
    split_mbu_label,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return load_lsblk((FIXTURES / name).read_text())


def test_named_inventory():
    inv = _load("lsblk_named.json")
    assert inv.live_disk == "sda"
    assert inv.live_set == "main"
    assert inv.live_functions == ["efi", "root", "home", "swap"]
    assert inv.backup_sets == ["bak1"]
    assert inv.unnamed_live is False
    assert inv.multiple_backup_sets is False
    assert inv.status_line == "Backup disk `bak1` is connected"
    assert inv.start_blocked_reason is None


def test_unnamed_blocks_start():
    inv = _load("lsblk_unnamed.json")
    assert inv.live_disk == "sda"
    assert inv.live_set is None
    assert inv.unnamed_live is True
    assert inv.backup_sets == []
    assert inv.status_line == "Plug in the backup disk"
    assert "Set up this computer" in (inv.start_blocked_reason or "")


def test_two_backup_sets_block_start():
    inv = _load("lsblk_two_backups.json")
    assert inv.multiple_backup_sets is True
    assert set(inv.backup_sets) == {"bak1", "bak2"}
    assert "Unplug the extras" in (inv.start_blocked_reason or "")


def test_split_and_set_name():
    assert split_mbu_label("main-root") == ("main", "root")
    assert split_mbu_label("main") is None
    assert split_mbu_label(None) is None
    assert is_valid_set_name("bak1") is True
    assert is_valid_set_name("bak-1") is False
    assert is_valid_set_name("bak 1") is False


def test_propose_labels_only_live_disk():
    inv = _load("lsblk_unnamed.json")
    labels = propose_labels(inv, "main")
    by_mount = {p.mountpoint: name for p, name in labels}
    assert by_mount["/"] == "main-root"
    assert by_mount["/home"] == "main-home"
    assert by_mount["/boot/efi"] == "main-efi"
    assert all(p.disk == "sda" for p, _ in labels)


def test_candidate_backup_disks_excludes_live():
    inv = _load("lsblk_named.json")
    names = [d.name for d in candidate_backup_disks(inv)]
    assert names == ["sdb"]


def test_empty_inventory_reason():
    inv = Inventory.empty("lsblk failed")
    assert inv.start_blocked_reason == "lsblk failed"


def test_candidate_backup_disks_empty_when_live_unknown():
    inv = Inventory.empty("lsblk failed")
    assert candidate_backup_disks(inv) == []
    named = _load("lsblk_named.json")
    unknown = replace(named, live_disk=None)
    assert unknown.disks
    assert candidate_backup_disks(unknown) == []
    no_root = _load("lsblk_no_root.json")
    assert no_root.live_disk is None
    assert candidate_backup_disks(no_root) == []


def test_separate_efi_and_swap_disk_is_not_a_format_candidate():
    """root is on nvme0n1 but sda holds /boot/efi and active swap."""
    inv = _load("lsblk_split_boot.json")
    assert inv.live_disk == "nvme0n1"
    assert set(inv.system_disks) == {"nvme0n1", "sda"}
    assert [d.name for d in candidate_backup_disks(inv)] == ["sdb"]


def test_every_member_of_a_spanning_vg_is_excluded():
    """The LV carrying / appears under both PVs; neither disk may be erased."""
    inv = _load("lsblk_vg_spans_two_disks.json")
    assert inv.live_disk == "sda"
    assert set(inv.system_disks) == {"sda", "sdb"}
    assert [d.name for d in candidate_backup_disks(inv)] == ["sdc"]


def test_removable_automounts_stay_formattable():
    """A desktop automount under /media is the disk the user wants to prepare."""
    inv = parse_lsblk(
        {
            "blockdevices": [
                {
                    "name": "sda",
                    "type": "disk",
                    "size": "256G",
                    "serial": "SYS0",
                    "children": [
                        {"name": "sda1", "type": "part", "mountpoint": "/", "partlabel": "main-root", "partn": 1}
                    ],
                },
                {
                    "name": "sdb",
                    "type": "disk",
                    "size": "32G",
                    "serial": "USB1",
                    "children": [
                        {"name": "sdb1", "type": "part", "mountpoint": "/media/alex/STICK", "partn": 1}
                    ],
                },
                {
                    "name": "sdc",
                    "type": "disk",
                    "size": "32G",
                    "serial": "USB2",
                    "children": [
                        {"name": "sdc1", "type": "part", "mountpoint": "/run/media/alex/OTHER", "partn": 1}
                    ],
                },
            ]
        }
    )
    assert inv.system_disks == ["sda"]
    assert [d.name for d in candidate_backup_disks(inv)] == ["sdb", "sdc"]


def test_disk_mounted_somewhere_unexpected_is_treated_as_system():
    inv = parse_lsblk(
        {
            "blockdevices": [
                {
                    "name": "sda",
                    "type": "disk",
                    "serial": "SYS0",
                    "children": [
                        {"name": "sda1", "type": "part", "mountpoint": "/", "partlabel": "main-root", "partn": 1}
                    ],
                },
                {
                    "name": "sdb",
                    "type": "disk",
                    "serial": "DATA",
                    "children": [{"name": "sdb1", "type": "part", "mountpoint": "/srv/data", "partn": 1}],
                },
            ]
        }
    )
    assert set(inv.system_disks) == {"sda", "sdb"}
    assert candidate_backup_disks(inv) == []


def test_multiple_mountpoints_are_all_considered():
    """btrfs subvolumes: MOUNTPOINT shows one, MOUNTPOINTS shows them all."""
    inv = parse_lsblk(
        {
            "blockdevices": [
                {
                    "name": "sda",
                    "type": "disk",
                    "serial": "SYS0",
                    "children": [
                        {
                            "name": "sda1",
                            "type": "part",
                            "mountpoint": "/home",
                            "mountpoints": ["/home", "/"],
                            "partlabel": "main-root",
                            "partn": 1,
                        }
                    ],
                }
            ]
        }
    )
    assert inv.live_disk == "sda"
    assert inv.system_disks == ["sda"]


def test_inactive_swap_on_a_spare_disk_stays_formattable():
    inv = _load("lsblk_named.json")
    assert set(inv.system_disks) == {"sda"}
    assert [d.name for d in candidate_backup_disks(inv)] == ["sdb"]


def test_disk_id_prefers_wwn_then_serial_then_ptuuid():
    inv = _load("lsblk_named.json")
    by_name = {d.name: d for d in inv.disks}
    assert by_name["sda"].disk_id == "wwn:0x5000aaaa1111bbbb"  # sda has a wwn
    assert by_name["sdb"].disk_id == "serial:usb1111backupb"  # sdb has none
    only_ptuuid = parse_lsblk(
        {
            "blockdevices": [
                {"name": "sdz", "type": "disk", "size": "1G", "ptuuid": "ABCD-1234"}
            ]
        }
    )
    assert only_ptuuid.disks[0].disk_id == "ptuuid:abcd-1234"


def test_disk_id_is_none_without_any_persistent_identifier():
    inv = parse_lsblk(
        {
            "blockdevices": [
                {"name": "sdz", "type": "disk", "size": "1G", "serial": "  ", "wwn": None}
            ]
        }
    )
    assert inv.disks[0].disk_id is None
    assert confirm_token(inv.disks[0]) is None


def test_confirm_token_is_tail_of_hardware_id():
    inv = _load("lsblk_named.json")
    sdb = next(d for d in inv.disks if d.name == "sdb")
    assert confirm_token(sdb) == "1backupb"
    assert len(confirm_token(sdb)) == 8


def test_disks_with_id_lookup():
    inv = _load("lsblk_named.json")
    assert [d.name for d in disks_with_id(inv, "serial:usb1111backupb")] == ["sdb"]
    assert [d.name for d in disks_with_id(inv, "SERIAL:USB1111BACKUPB")] == ["sdb"]
    assert disks_with_id(inv, "serial:nope") == []
    assert disks_with_id(inv, "") == []


def test_next_step_offers_the_action_that_unblocks_each_state():
    from mbu_gui.disks import next_step

    unnamed = _load("lsblk_unnamed.json")
    assert next_step(unnamed).action == "setup"
    assert next_step(unnamed).enabled

    ready = _load("lsblk_named.json")
    assert next_step(ready).action == "backup"
    assert next_step(ready).enabled
    assert "bak1" in next_step(ready).detail

    no_disk = replace(ready, backup_sets=[])
    assert next_step(no_disk).action == "format"
    assert next_step(no_disk).enabled

    several = _load("lsblk_two_backups.json")
    assert next_step(several).action == "blocked"
    assert not next_step(several).enabled


def test_mbr_live_disk_is_reported_instead_of_looping_through_setup():
    """The dead end that made setup fail silently on every attempt.

    MBR partitions have no name field, so sfdisk reports success, rewrites the
    table and drops the name. The disk then still looks unnamed, so the app
    sent the user back to Set up this computer forever.
    """
    from mbu_gui.disks import live_disk_unsupported, next_step

    inv = _load("lsblk_mbr_live.json")
    assert inv.live_disk == "vda"
    assert inv.live_pttype == "dos"

    reason = live_disk_unsupported(inv)
    assert reason is not None
    assert "MBR" in reason
    assert "GPT" in reason

    # Must be reported ahead of the unnamed case, and offer no action.
    assert inv.unnamed_live
    step = next_step(inv)
    assert step.action == "blocked"
    assert not step.enabled
    assert "MBR" in step.detail
    assert "MBR" in (inv.start_blocked_reason or "")
    assert "MBR" in inv.status_line


def test_gpt_live_disk_is_not_reported_as_unsupported():
    from mbu_gui.disks import live_disk_unsupported

    assert live_disk_unsupported(_load("lsblk_named.json")) is None
    # A fixture with no PTTYPE at all must not be treated as unsupported.
    assert live_disk_unsupported(_load("lsblk_unnamed.json")) is None


def test_setup_page_refuses_an_mbr_disk():
    from mbu_gui.disks import setup_block_reason

    inv = _load("lsblk_mbr_live.json")
    reason = setup_block_reason(inv, "main", "main")
    assert reason is not None and "MBR" in reason


def test_next_step_never_offers_a_way_past_the_clone_guard():
    """Booting from a clone must not produce a clickable primary button.

    The guard is the only thing standing between a booted clone and rsync
    running backwards over the real system disk, so an inventory carrying an
    unexplained block has to stay disabled rather than fall through to backup.
    """
    from mbu_gui.disks import next_step

    ready = _load("lsblk_named.json")
    guarded = replace(ready, start_blocked_reason="This computer is recorded as set `main`")
    step = next_step(guarded)
    assert step.action == "blocked"
    assert not step.enabled
    assert "recorded as set" in step.detail


def test_luks_lvm_root_marks_sda_live_and_not_a_format_candidate():
    inv = _load("lsblk_luks_lvm.json")
    assert inv.live_disk == "sda"
    names = [d.name for d in candidate_backup_disks(inv)]
    assert "sda" not in names
    assert names == ["sdb"]
    part_names = [p.name for d in inv.disks if d.name == "sda" for p in d.partitions]
    assert part_names == ["sda1", "sda2", "sda3"]
