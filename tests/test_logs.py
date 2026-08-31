# tests/test_logs.py
from mbu_gui.logs import current_file_from_line, last_run_label, parse_master_log

LOG = """
2025/01/07-10:00:00 START BACKUP FROM main TO bak1
2025/01/07-10:05:00 DONE- BACKUP FROM main TO bak1 : efi root home
2025/01/08-12:00:00 START BACKUP FROM main TO bak1
"""


def test_parse_incomplete_last_start():
    run = parse_master_log(LOG)
    assert run is not None
    assert run.ok is False
    assert run.from_set == "main"
    assert run.to_set == "bak1"
    assert run.timestamp == "2025/01/08-12:00:00"


def test_parse_last_done_wins():
    text = LOG + "2025/01/08-12:20:00 DONE- BACKUP FROM main TO bak1 : root home\n"
    run = parse_master_log(text)
    assert run is not None
    assert run.ok is True
    assert run.functions == "root home"
    assert last_run_label(run) == "Last backup: 2025/01/08-12:20:00  main → bak1"


def test_empty_log():
    assert parse_master_log("") is None
    assert last_run_label(None) == "No backup yet"


def test_current_file():
    assert current_file_from_line("home/alex/.bashrc") == "home/alex/.bashrc"
    assert current_file_from_line("sent 123 bytes") is None
    assert current_file_from_line("START Directory SYNC FROM / TO /mnt") is None
    assert current_file_from_line("some/dir/") is None
