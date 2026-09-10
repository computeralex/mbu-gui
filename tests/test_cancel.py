import json
import signal

from mbu_gui_helper.cancel import (
    cancel_run,
    clear_run,
    no_run_text,
    read_run,
    record_run,
    reused_pid_text,
    stale_run_text,
    start_ticks,
)


def _fake_proc(tmp_path, pid, started, name="mbup"):
    """A /proc/<pid>/stat close enough for the field counting to matter.

    Real layout is `pid (comm) state ...`, so the first field after the closing
    bracket is state (field 3) and starttime (field 22) is 19 further along.
    """
    entry = tmp_path / str(pid)
    entry.mkdir(parents=True, exist_ok=True)
    after_name = ["S"] + ["0"] * 49
    after_name[19] = str(started)
    (entry / "stat").write_text(f"{pid} ({name}) " + " ".join(after_name) + "\n")
    return tmp_path


def test_start_time_is_read_from_the_right_field(tmp_path):
    _fake_proc(tmp_path, 4242, 998877)
    assert start_ticks(4242, tmp_path) == 998877


def test_a_bracketed_space_filled_name_does_not_shift_the_fields(tmp_path):
    _fake_proc(tmp_path, 7, 555, name="rsync (to) x")
    assert start_ticks(7, tmp_path) == 555


def test_missing_process_has_no_start_time(tmp_path):
    assert start_ticks(999, tmp_path) is None


def test_cancel_signals_the_whole_group_not_one_process(tmp_path):
    """rsync is a grandchild, so signalling only the shell would not stop it."""
    _fake_proc(tmp_path, 300, 12345)
    record = tmp_path / "run.json"
    record_run(record, 300, proc_root=tmp_path)
    sent = []
    assert cancel_run(record, proc_root=tmp_path, kill=lambda *a: sent.append(a)) is None
    assert sent == [(300, signal.SIGTERM)]


def test_cancel_without_a_run_says_so(tmp_path):
    assert cancel_run(tmp_path / "missing.json", proc_root=tmp_path) == no_run_text


def test_cancel_after_the_backup_already_stopped(tmp_path):
    record = tmp_path / "run.json"
    record.write_text(json.dumps({"pgid": 4321, "start": 11}))
    sent = []
    message = cancel_run(record, proc_root=tmp_path, kill=lambda *a: sent.append(a))
    assert message == stale_run_text
    assert sent == []


def test_a_recycled_pid_is_never_signalled(tmp_path):
    """The dangerous case: the backup ended and the number was handed on.

    Without the start-time check this would send SIGTERM, as root, to whatever
    unrelated process group inherited the number.
    """
    _fake_proc(tmp_path, 500, 1000)
    record = tmp_path / "run.json"
    record_run(record, 500, proc_root=tmp_path)
    _fake_proc(tmp_path, 500, 9999)  # same number, different process
    sent = []
    message = cancel_run(record, proc_root=tmp_path, kill=lambda *a: sent.append(a))
    assert message == reused_pid_text
    assert sent == []


def test_a_corrupt_record_is_not_treated_as_a_pid(tmp_path):
    record = tmp_path / "run.json"
    for junk in ("", "not json", "[]", '{"pgid": "300"}', '{"pgid": 1}', '{"pgid": -1}'):
        record.write_text(junk)
        sent = []
        message = cancel_run(record, proc_root=tmp_path, kill=lambda *a: sent.append(a))
        assert message == no_run_text
        assert sent == []


def test_clearing_a_run_leaves_nothing_to_signal(tmp_path):
    _fake_proc(tmp_path, 600, 1)
    record = tmp_path / "run.json"
    record_run(record, 600, proc_root=tmp_path)
    assert read_run(record) is not None
    clear_run(record)
    assert cancel_run(record, proc_root=tmp_path) == no_run_text
