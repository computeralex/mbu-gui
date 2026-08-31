# tests/test_disks.py
from pathlib import Path

from mbu_gui.disks import (
    Inventory,
    candidate_backup_disks,
    is_valid_set_name,
    load_lsblk,
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
