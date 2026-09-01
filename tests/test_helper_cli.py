from pathlib import Path
from types import SimpleNamespace
import json
import os
import stat

from mbu_gui_helper.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
FAKE = Path(__file__).parent / "fake_mbu"


def _env(tmp_path):
    return {
        "HOME": str(tmp_path / "home"),
        "MBU_GUI_MBU_DIR": str(FAKE),
        "PATH": os.environ.get("PATH", "/usr/bin"),
    }


def _lsblk(name="lsblk_named.json"):
    return json.loads((FIXTURES / name).read_text())


def test_backup_runs_mbup_then_clean(tmp_path, capsys):
    code = main(
        ["backup", "--fselection", "-bootfix,root,home"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "fake-mbup args:" in out
    assert "fselection=-bootfix,root,home" in out
    assert "fake-mbuclean" in out


SDA_ID = "wwn:0x5000aaaa1111bbbb"  # sda reports a wwn, which wins over its serial
SDB_ID = "serial:usb1111backupb"


def test_format_disk_refuses_live(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sda", "--disk-id", SDA_ID, "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
    )
    assert code == 2
    assert "contains /" in capsys.readouterr().out


def test_format_disk_refuses_when_live_unknown(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", SDB_ID, "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk("lsblk_no_root.json"),
    )
    assert code == 2
    assert "contains /" in capsys.readouterr().out


def test_format_disk_refuses_luks_lvm_live_sda(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sda", "--disk-id", SDA_ID, "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk("lsblk_luks_lvm.json"),
    )
    assert code == 2
    assert "contains /" in capsys.readouterr().out


def test_format_disk_allows_sdb_when_root_is_luks_lvm(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", SDB_ID, "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk("lsblk_luks_lvm.json"),
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "mbuFormatDisk" in out
    assert "disk=sdb" in out


def test_format_disk_allows_sdb(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", SDB_ID, "--pset", "bak1"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "mbuFormatTableWrite" in out
    assert "mbuFormatDisk" in out
    assert "disk=sdb" in out
    assert "fake-mbuclean" in out


def test_format_disk_refuses_when_device_renamed(tmp_path, capsys):
    """GUI saw the target as sdb; by now that hardware id is sdc."""
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", "serial:usb2222backupc", "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk("lsblk_two_backups.json"),
    )
    assert code == 2
    assert "changed device name" in capsys.readouterr().out


def test_format_disk_refuses_unknown_hardware_id(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", "serial:notplugged", "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
    )
    assert code == 2
    assert "no attached disk has that hardware id" in capsys.readouterr().out


def test_format_disk_refuses_empty_hardware_id(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", "", "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
    )
    assert code == 2
    assert "no serial number" in capsys.readouterr().out


def test_format_disk_does_not_run_mbu_when_id_check_fails(tmp_path):
    calls = []
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", "serial:notplugged", "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda argv, **kwargs: calls.append(list(argv)) or 0,
    )
    assert code == 2
    assert calls == []


def test_format_disk_cleans_after_format_failure(tmp_path):
    calls = []

    def run(argv, **kwargs):
        calls.append(list(argv))
        if argv[0] == "./mbulib" and "mbuFormatDisk" in argv:
            return 7
        return 0

    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", SDB_ID, "--pset", "bak1"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=run,
    )
    assert code == 7
    assert ["./mbuclean"] in calls
    assert any("mbuFormatDisk" in argv for argv in calls)


def test_label_live_refuses_sdb(tmp_path, capsys):
    named = _lsblk()
    # pick a backup partition name from fixture, e.g. sdb1
    code = main(
        ["label-live", "--labels", "sdb1=main-root"],
        environ=_env(tmp_path),
        lsblk_data=named,
        run=lambda *a, **k: 0,
    )
    assert code == 2
    assert "not on the disk that contains /" in capsys.readouterr().out


def test_label_live_sfdisk_argv(tmp_path):
    captured = []
    def run(argv, **kwargs):
        captured.append(argv)
        return 0
    inv = _lsblk("lsblk_unnamed.json")
    # use a live partition name from unnamed fixture, partn 2 if that is /
    code = main(
        ["label-live", "--labels", "sda2=main-root"],
        environ=_env(tmp_path),
        lsblk_data=inv,
        run=run,
    )
    assert code == 0
    assert captured[0][0] == "sfdisk"
    assert "--part-label" in captured[0]
    assert captured[0] == ["sfdisk", "--part-label", "/dev/sda", "2", "main-root"]


def test_chown_state_dirs_to_pkexec_uid(tmp_path, monkeypatch):
    home = tmp_path / "axel"
    owned = []

    def getpwuid(uid):
        assert uid == 1000
        return SimpleNamespace(pw_dir=str(home), pw_gid=1000)

    def fake_chown(path, uid, gid, follow_symlinks=True):
        owned.append((str(path), uid, gid, follow_symlinks))

    monkeypatch.setattr("mbu_gui.paths.pwd.getpwuid", getpwuid)
    monkeypatch.setattr("mbu_gui_helper.cli.pwd.getpwuid", getpwuid)
    monkeypatch.setattr("mbu_gui_helper.cli.os.chown", fake_chown)
    env = _env(tmp_path)
    env["PKEXEC_UID"] = "1000"
    state = home / ".local/share/mbu-gui"
    (state / "log").mkdir(parents=True)
    (state / "out").mkdir(parents=True)
    mount = state / "mount"
    mount.mkdir(parents=True)
    trapped = mount / "bak1-root"
    trapped.mkdir()
    (trapped / "passwd").write_text("should not be chowned")
    (state / "log" / "mbu.log").write_text("ok")
    (state / "out" / "table").write_text("t")
    code = main(
        ["clean"],
        environ=env,
        lsblk_data=_lsblk(),
        run=lambda *a, **k: 0,
    )
    assert code == 0
    chowned = {Path(p) for p, uid, gid, _ in owned}
    assert state in chowned
    assert state / "log" in chowned
    assert state / "out" in chowned
    assert state / "mount" in chowned
    assert state / "log" / "mbu.log" in chowned
    assert state / "out" / "table" in chowned
    assert trapped not in chowned
    assert trapped / "passwd" not in chowned
    assert all(uid == 1000 and gid == 1000 and follow is False for _, uid, gid, follow in owned)


def test_no_chown_without_pkexec_uid(tmp_path, monkeypatch):
    owned = []
    monkeypatch.setattr(
        "mbu_gui_helper.cli.os.chown",
        lambda path, uid, gid: owned.append(path),
    )
    code = main(
        ["clean"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda *a, **k: 0,
    )
    assert code == 0
    assert owned == []
