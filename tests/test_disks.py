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


def test_luks_lvm_root_marks_sda_live_and_not_a_format_candidate():
    inv = _load("lsblk_luks_lvm.json")
    assert inv.live_disk == "sda"
    names = [d.name for d in candidate_backup_disks(inv)]
    assert "sda" not in names
    assert names == ["sdb"]
    part_names = [p.name for d in inv.disks if d.name == "sda" for p in d.partitions]
    assert part_names == ["sda1", "sda2", "sda3"]
