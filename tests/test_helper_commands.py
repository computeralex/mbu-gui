from pathlib import Path

from mbu_gui.disks import Inventory, load_lsblk
from mbu_gui.paths import resolve_paths
from mbu_gui_helper.commands import (
    format_disk_argv,
    mbuclean_argv,
    mbumount_argv,
    mbup_argv,
    mbu_environ,
    sfdisk_label_argv,
)
from mbu_gui_helper.safety import (
    ambiguous_disk_id_error,
    assert_label_targets_live,
    assert_not_system_disk,
    label_wrong_disk_error,
    live_disk_error,
    missing_disk_id_error,
    renamed_disk_error,
    resolve_format_target,
    system_disk_error,
    unknown_disk_id_error,
)

FIXTURES = Path(__file__).parent / "fixtures"


def named():
    return load_lsblk((FIXTURES / "lsblk_named.json").read_text())


def two_backups():
    return load_lsblk((FIXTURES / "lsblk_two_backups.json").read_text())


def _raises(fn, message):
    try:
        fn()
    except ValueError as e:
        assert str(e) == message, f"got {e!r}, wanted {message!r}"
        return
    assert False, f"expected ValueError: {message}"


def test_resolve_format_target_matches_hardware_id():
    inv = named()
    assert resolve_format_target("serial:usb1111backupb", "sdb", inv) == "sdb"
    assert resolve_format_target("SERIAL:USB1111BACKUPB", "/dev/sdb", inv) == "sdb"


def test_resolve_format_target_refuses_renamed_device():
    """The id now belongs to sdc, but the GUI expected sdb: abort, do not guess."""
    inv = two_backups()
    _raises(
        lambda: resolve_format_target("serial:usb2222backupc", "sdb", inv),
        renamed_disk_error,
    )


def test_resolve_format_target_refuses_unknown_or_empty_id():
    inv = named()
    _raises(lambda: resolve_format_target("serial:gone", "sdb", inv), unknown_disk_id_error)
    _raises(lambda: resolve_format_target("", "sdb", inv), missing_disk_id_error)
    _raises(lambda: resolve_format_target("   ", "sdb", inv), missing_disk_id_error)


def test_resolve_format_target_refuses_duplicate_ids():
    from dataclasses import replace

    inv = two_backups()
    clashing = [
        replace(d, serial="USB1111BACKUPB") if d.name in ("sdb", "sdc") else d
        for d in inv.disks
    ]
    inv = replace(inv, disks=clashing)
    _raises(
        lambda: resolve_format_target("serial:usb1111backupb", "sdb", inv),
        ambiguous_disk_id_error,
    )


def test_refuse_format_live_disk():
    inv = named()
    _raises(lambda: assert_not_system_disk("sda", inv), live_disk_error)
    _raises(lambda: assert_not_system_disk("/dev/sda", inv), live_disk_error)
    assert_not_system_disk("sdb", inv)  # does not raise


def test_refuse_format_when_live_disk_unknown():
    inv = Inventory.empty("could not find /")
    for name in ("sda", "sdb", "/dev/nvme0n1"):
        _raises(lambda n=name: assert_not_system_disk(n, inv), live_disk_error)
    no_root = load_lsblk((FIXTURES / "lsblk_no_root.json").read_text())
    assert no_root.live_disk is None
    _raises(lambda: assert_not_system_disk("sdb", no_root), live_disk_error)


def test_refuse_format_disk_holding_efi_or_swap_but_not_root():
    inv = load_lsblk((FIXTURES / "lsblk_split_boot.json").read_text())
    _raises(lambda: assert_not_system_disk("sda", inv), system_disk_error)
    _raises(lambda: assert_not_system_disk("/dev/sda", inv), system_disk_error)
    _raises(lambda: assert_not_system_disk("nvme0n1", inv), live_disk_error)
    assert_not_system_disk("sdb", inv)  # the actual spare


def test_refuse_format_second_member_of_spanning_vg():
    inv = load_lsblk((FIXTURES / "lsblk_vg_spans_two_disks.json").read_text())
    _raises(lambda: assert_not_system_disk("sdb", inv), system_disk_error)
    assert_not_system_disk("sdc", inv)


def test_refuse_label_on_backup_disk():
    inv = named()
    try:
        assert_label_targets_live("sdb1", inv)
        assert False, "expected ValueError"
    except ValueError as e:
        assert str(e) == label_wrong_disk_error
    part = assert_label_targets_live("sda2", inv)
    assert part.name == "sda2"


def test_mbup_argv():
    assert mbup_argv("-bootfs,root,home") == ["./mbup", "ask=n", "fselection=-bootfs,root,home"]
    assert mbuclean_argv() == ["./mbuclean"]
    assert mbumount_argv("bak1") == ["./mbumount", "bak1"]
    assert format_disk_argv("/dev/sdb", "bak1", "/tmp/t") == [
        "./mbulib", "mbuFormatDisk", "fake=n", "disk=sdb", "pset=bak1", "tablefile=/tmp/t",
    ]
    assert sfdisk_label_argv("sda", 1, "main-efi") == [
        "sfdisk", "--part-label", "/dev/sda", "1", "main-efi",
    ]


def test_mbu_environ(tmp_path):
    paths = resolve_paths(state_dir=tmp_path / "state", mbu_dir=tmp_path / "mbu")
    env = mbu_environ(paths, {"PATH": "/usr/bin", "HOME": "/root"})
    assert env["mbuDir"] == str(paths.mbu_dir)
    assert env["mbuLogDir"] == str(paths.log_dir)
    assert env["mbuDoRsyncVerbose"] == "y"
    assert env["HOME"] == "/root"
