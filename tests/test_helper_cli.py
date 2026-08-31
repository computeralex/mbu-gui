from pathlib import Path
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


def test_format_disk_refuses_live(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sda", "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
    )
    assert code == 2
    assert "contains /" in capsys.readouterr().out


def test_format_disk_allows_sdb(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sdb", "--pset", "bak1"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "mbuFormatTableWrite" in out
    assert "mbuFormatDisk" in out
    assert "disk=sdb" in out
    assert "fake-mbuclean" in out


def test_format_disk_cleans_after_format_failure(tmp_path):
    calls = []

    def run(argv, **kwargs):
        calls.append(list(argv))
        if argv[0] == "./mbulib" and "mbuFormatDisk" in argv:
            return 7
        return 0

    code = main(
        ["format-disk", "--disk", "sdb", "--pset", "bak1"],
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
