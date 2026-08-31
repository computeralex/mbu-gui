from pathlib import Path

from mbu_gui.disks import load_lsblk
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
    assert_label_targets_live,
    assert_not_live_disk,
    label_wrong_disk_error,
    live_disk_error,
)

FIXTURES = Path(__file__).parent / "fixtures"


def named():
    return load_lsblk((FIXTURES / "lsblk_named.json").read_text())


def test_refuse_format_live_disk():
    inv = named()
    try:
        assert_not_live_disk("sda", inv)
        assert False, "expected ValueError"
    except ValueError as e:
        assert str(e) == live_disk_error
    try:
        assert_not_live_disk("/dev/sda", inv)
        assert False, "expected ValueError"
    except ValueError as e:
        assert str(e) == live_disk_error
    assert_not_live_disk("sdb", inv)  # does not raise


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
    paths = resolve_paths(home=tmp_path, mbu_dir=tmp_path / "mbu")
    env = mbu_environ(paths, {"PATH": "/usr/bin", "HOME": "/root"})
    assert env["mbuDir"] == str(paths.mbu_dir)
    assert env["mbuLogDir"] == str(paths.log_dir)
    assert env["mbuDoRsyncVerbose"] == "y"
    assert env["HOME"] == "/root"
