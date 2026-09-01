from pathlib import Path
import json
import os

from mbu_gui_helper.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
FAKE = Path(__file__).parent / "fake_mbu"


def _env(tmp_path):
    return {
        "HOME": str(tmp_path / "home"),
        "MBU_GUI_MBU_DIR": str(FAKE),
        "PATH": os.environ.get("PATH", "/usr/bin"),
    }


def _state(tmp_path):
    return tmp_path / "var-lib-mbu-gui"


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


def test_format_disk_refuses_disk_holding_efi_and_swap(tmp_path, capsys):
    """sda has no / on it, but it carries /boot/efi and active swap."""
    calls = []
    code = main(
        ["format-disk", "--disk", "sda", "--disk-id", SDA_ID, "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk("lsblk_split_boot.json"),
        run=lambda argv, **k: calls.append(list(argv)) or 0,
    )
    assert code == 2
    assert "running system is using" in capsys.readouterr().out
    assert calls == []


def test_format_disk_refuses_second_member_of_spanning_vg(tmp_path, capsys):
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", "wwn:0x5000aaaa1111cccc", "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk("lsblk_vg_spans_two_disks.json"),
    )
    assert code == 2
    assert "running system is using" in capsys.readouterr().out


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


def test_first_backup_records_this_machine(tmp_path):
    state = _state(tmp_path)
    code = main(
        ["backup", "--fselection", "root"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda *a, **k: 0,
        state_dir=state,
    )
    assert code == 0
    record = json.loads((state / "machine.json").read_text())
    assert record["machine_set"] == "main"
    assert record["disk_id"] == "wwn:0x5000aaaa1111bbbb"


def test_backup_refused_when_running_from_the_clone(tmp_path, capsys):
    """Booted from bak1 with the internal disk attached: roles are inverted."""
    state = _state(tmp_path)
    state.mkdir(parents=True)
    (state / "machine.json").write_text(json.dumps({"machine_set": "main"}) + "\n")
    inverted = _lsblk()
    # Swap which disk carries /: the backup set bak1 is now the running root.
    for dev in inverted["blockdevices"]:
        for child in dev.get("children") or []:
            if child.get("mountpoint") == "/":
                child["mountpoint"] = None
            if child.get("partlabel") == "bak1-root":
                child["mountpoint"] = "/"
    calls = []
    code = main(
        ["backup", "--fselection", "-bootfix,root"],
        environ=_env(tmp_path),
        lsblk_data=inverted,
        run=lambda argv, **k: calls.append(list(argv)) or 0,
        state_dir=state,
    )
    assert code == 2
    out = capsys.readouterr().out
    assert "recorded as set `main`" in out
    assert "running from set `bak1`" in out
    assert calls == []
    assert not (state / "backup-incomplete").exists()


def test_backup_allowed_when_record_matches(tmp_path):
    state = _state(tmp_path)
    state.mkdir(parents=True)
    (state / "machine.json").write_text(json.dumps({"machine_set": "main"}) + "\n")
    code = main(
        ["backup", "--fselection", "root"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda *a, **k: 0,
        state_dir=state,
    )
    assert code == 0


def test_corrupt_machine_record_refuses_backup(tmp_path, capsys):
    state = _state(tmp_path)
    state.mkdir(parents=True)
    (state / "machine.json").write_text("not json")
    calls = []
    code = main(
        ["backup", "--fselection", "root"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda argv, **k: calls.append(list(argv)) or 0,
        state_dir=state,
    )
    assert code == 2
    assert "Refusing to back up" in capsys.readouterr().out
    assert calls == []


def test_label_live_records_the_chosen_set(tmp_path):
    state = _state(tmp_path)
    code = main(
        ["label-live", "--labels", "sda2=newname-root,sda1=newname-efi"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk("lsblk_unnamed.json"),
        run=lambda *a, **k: 0,
        state_dir=state,
    )
    assert code == 0
    record = json.loads((state / "machine.json").read_text())
    assert record["machine_set"] == "newname"


def test_failed_label_live_does_not_record(tmp_path):
    state = _state(tmp_path)
    code = main(
        ["label-live", "--labels", "sda2=newname-root"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk("lsblk_unnamed.json"),
        run=lambda *a, **k: 9,
        state_dir=state,
    )
    assert code == 9
    assert not (state / "machine.json").exists()


def test_backup_marker_written_before_run_and_cleared_on_success(tmp_path):
    state = _state(tmp_path)
    marker = state / "backup-incomplete"
    seen = {}

    def run(argv, **kwargs):
        if argv[0] == "./mbup":
            seen["marker_during_run"] = marker.exists()
        return 0

    code = main(
        ["backup", "--fselection", "-bootfix,root"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=run,
        state_dir=state,
    )
    assert code == 0
    assert seen["marker_during_run"] is True
    assert not marker.exists()


def test_backup_marker_survives_a_failed_run(tmp_path):
    state = _state(tmp_path)
    marker = state / "backup-incomplete"
    code = main(
        ["backup", "--fselection", "-bootfix,root"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda argv, **k: 5 if argv[0] == "./mbup" else 0,
        state_dir=state,
    )
    assert code == 5
    assert marker.exists()


def test_backup_marker_survives_a_failed_unmount_after_a_good_copy(tmp_path):
    """mbuclean failing must not be reported as safe to leave plugged in."""
    state = _state(tmp_path)
    marker = state / "backup-incomplete"
    code = main(
        ["backup", "--fselection", "root"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda argv, **k: 3 if argv[0] == "./mbuclean" else 0,
        state_dir=state,
    )
    assert code == 3
    assert marker.exists()


def test_format_does_not_write_the_backup_marker(tmp_path):
    """Formatting does not clone UUIDs, so it must not raise the warning."""
    state = _state(tmp_path)
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", SDB_ID, "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda *a, **k: 0,
        state_dir=state,
    )
    assert code == 0
    assert not (state / "backup-incomplete").exists()


def test_state_dirs_are_created_under_root_owned_state(tmp_path):
    state = _state(tmp_path)
    code = main(
        ["clean"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda *a, **k: 0,
        state_dir=state,
    )
    assert code == 0
    for sub in ("log", "out", "mount"):
        assert (state / sub).is_dir()
    # nothing was created in the calling user's home
    assert not (tmp_path / "home" / ".local").exists()


def test_state_dir_ignores_home_env(tmp_path):
    """PKEXEC_UID/HOME must not steer root's writes into a user's home."""
    env = _env(tmp_path)
    env["PKEXEC_UID"] = "1000"
    state = _state(tmp_path)
    code = main(
        ["clean"],
        environ=env,
        lsblk_data=_lsblk(),
        run=lambda *a, **k: 0,
        state_dir=state,
    )
    assert code == 0
    assert (state / "log").is_dir()
    assert not (tmp_path / "home" / ".local").exists()


def test_refuses_symlinked_state_subdirectory(tmp_path, capsys):
    """A symlinked log dir would aim root's MBU log writes anywhere."""
    state = _state(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    state.mkdir(parents=True)
    (state / "log").symlink_to(elsewhere, target_is_directory=True)
    calls = []
    code = main(
        ["clean"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda argv, **k: calls.append(list(argv)) or 0,
        state_dir=state,
    )
    assert code == 2
    assert "Refusing to use a state path" in capsys.readouterr().out
    assert calls == []


def test_refuses_symlinked_state_root(tmp_path, capsys):
    state = _state(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    state.parent.mkdir(parents=True, exist_ok=True)
    state.symlink_to(elsewhere, target_is_directory=True)
    code = main(
        ["clean"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda *a, **k: 0,
        state_dir=state,
    )
    assert code == 2
    assert "Refusing to use a state path" in capsys.readouterr().out


def test_format_table_is_cleared_before_use_and_lives_outside_home(tmp_path):
    state = _state(tmp_path)
    table = state / "out" / "mbuformat.table"
    table.parent.mkdir(parents=True)
    table.write_text("planted layout that root must not reuse\n")
    seen = {}

    def run(argv, **kwargs):
        if "mbuFormatTableWrite" in argv:
            seen["table_at_generate"] = table.exists()
        if "mbuFormatDisk" in argv:
            seen["tablefile_arg"] = [a for a in argv if a.startswith("tablefile=")]
        return 0

    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", SDB_ID, "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=run,
        state_dir=state,
    )
    assert code == 0
    assert seen["table_at_generate"] is False
    assert seen["tablefile_arg"] == [f"tablefile={table}"]
    assert ".local" not in str(table)


def test_refuses_symlinked_format_table(tmp_path, capsys):
    state = _state(tmp_path)
    (state / "out").mkdir(parents=True)
    target = tmp_path / "victim.conf"
    target.write_text("important\n")
    (state / "out" / "mbuformat.table").symlink_to(target)
    calls = []
    code = main(
        ["format-disk", "--disk", "sdb", "--disk-id", SDB_ID, "--pset", "bak9"],
        environ=_env(tmp_path),
        lsblk_data=_lsblk(),
        run=lambda argv, **k: calls.append(list(argv)) or 0,
        state_dir=state,
    )
    assert code == 2
    assert "Refusing to use a state path" in capsys.readouterr().out
    assert calls == []
    assert target.read_text() == "important\n"
