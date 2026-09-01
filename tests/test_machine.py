from dataclasses import replace
from pathlib import Path
import json

import pytest

from mbu_gui.disks import load_lsblk
from mbu_gui.machine import (
    CLONE_STATUS_LINE,
    MachineRecord,
    apply_machine_guard,
    corrupt_record_error,
    inversion_reason,
    live_disk_id,
    load_machine_record,
    record_for,
    record_path,
    save_machine_record,
)

FIXTURES = Path(__file__).parent / "fixtures"


def named():
    return load_lsblk((FIXTURES / "lsblk_named.json").read_text())


def test_record_round_trip(tmp_path):
    path = record_path(tmp_path)
    assert load_machine_record(path) is None
    save_machine_record(path, MachineRecord("main", "wwn:0x5000aaaa1111bbbb"))
    loaded = load_machine_record(path)
    assert loaded == MachineRecord("main", "wwn:0x5000aaaa1111bbbb")
    assert path.name == "machine.json"


def test_record_for_uses_live_set_and_live_disk_id():
    inv = named()
    assert live_disk_id(inv) == "wwn:0x5000aaaa1111bbbb"
    assert record_for(inv) == MachineRecord("main", "wwn:0x5000aaaa1111bbbb")


def test_record_for_is_none_when_live_set_unknown():
    inv = load_lsblk((FIXTURES / "lsblk_unnamed.json").read_text())
    assert record_for(inv) is None


def test_no_inversion_when_running_from_the_recorded_machine():
    inv = named()
    assert inversion_reason(MachineRecord("main"), inv) is None
    assert apply_machine_guard(inv, MachineRecord("main")) is inv


def test_inversion_detected_when_booted_from_the_clone():
    """Booted from bak1: the internal disk now looks like the backup target."""
    inv = named()
    booted_from_clone = replace(
        inv, live_set="bak1", live_disk="sdb", backup_sets=["main"]
    )
    reason = inversion_reason(MachineRecord("main"), booted_from_clone)
    assert reason is not None
    assert "recorded as set `main`" in reason
    assert "running from set `bak1`" in reason
    assert "unplug the backup disk" in reason.lower()

    guarded = apply_machine_guard(booted_from_clone, MachineRecord("main"))
    assert guarded.start_blocked_reason == reason
    assert guarded.status_line == CLONE_STATUS_LINE


def test_no_record_means_no_opinion_yet():
    inv = named()
    assert inversion_reason(None, inv) is None
    assert apply_machine_guard(inv, None) is inv


def test_corrupt_record_fails_closed(tmp_path):
    path = record_path(tmp_path)
    for bad in ("{", "[]", "{}", '{"machine_set": ""}', '{"machine_set": 7}'):
        path.write_text(bad)
        with pytest.raises(ValueError) as e:
            load_machine_record(path)
        assert str(e.value) == corrupt_record_error


def test_refuses_to_write_through_a_symlink(tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("keep me\n")
    path = record_path(tmp_path)
    path.symlink_to(victim)
    with pytest.raises(ValueError):
        save_machine_record(path, MachineRecord("main"))
    assert victim.read_text() == "keep me\n"


def test_disk_id_is_optional_in_the_record(tmp_path):
    path = record_path(tmp_path)
    path.write_text(json.dumps({"machine_set": "main"}) + "\n")
    assert load_machine_record(path) == MachineRecord("main", None)
