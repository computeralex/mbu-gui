# tests/test_logs.py
from mbu_gui.logs import (
    backup_summary,
    copied_bytes_from_lines,
    current_file_from_line,
    last_run_label,
    parse_master_log,
    plain_label_line,
    progress_label,
    route_sets_from_lines,
    strip_ansi,
    sync_target,
)

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


def test_sync_markers_name_the_partition_being_copied():
    assert sync_target("START Directory SYNC FROM /boot/efi TO /mnt/bak1/efi") == "efi"
    assert sync_target("START Directory SYNC FROM / TO /mnt/bak1/root/") == "root"
    assert sync_target("home/alex/.bashrc") is None
    assert sync_target("DONE- BACKUP FROM main TO bak1 : efi root") is None


def test_progress_label_reads_as_a_sentence():
    assert progress_label(1, 3, "efi", 0) == "Copying efi (1 of 3)"
    assert progress_label(2, 3, "root", 12345) == "Copying root (2 of 3) — 12,345 files so far"


def test_sfdisk_chatter_never_reaches_the_user():
    """The naming step printed six lines of partition-table plumbing.

    The two "busy" lines are the normal result of renaming the disk you booted
    from, but they read as a failure to anyone who is not a Linux admin.
    """
    noise = [
        "The partition table has been altered.",
        "Calling ioctl() to re-read partition table.",
        "Re-reading the partition table failed.: Device or resource busy",
        "The kernel still uses the old table. The new table will be used at "
        "the next reboot or after you run partprobe(8) or partx(8).",
        "Syncing disks.",
        "",
    ]
    assert [plain_label_line(line) for line in noise] == [None] * len(noise)


def test_a_rename_is_reported_in_plain_words():
    assert (
        plain_label_line("Partition name changed from '' to 'main-efi'.")
        == "Named this computer's main-efi partition"
    )
    assert (
        plain_label_line("Partition name changed from 'Winux' to 'main-root'.")
        == "Named this computer's main-root partition"
    )


def test_an_unrecognised_line_is_passed_through_untouched():
    """Quieting known noise must never swallow a real error."""
    for line in ("sfdisk: cannot open /dev/sda: No such file or directory",
                 "Permission denied"):
        assert plain_label_line(line) == line


def test_current_file():
    assert current_file_from_line("home/alex/.bashrc") == "home/alex/.bashrc"
    assert current_file_from_line("sent 123 bytes") is None
    assert current_file_from_line("START Directory SYNC FROM / TO /mnt") is None
    assert current_file_from_line("some/dir/") is None


def test_current_file_rejects_mbuclean_status_and_ansi_junk():
    """After a run the 'current file' line showed mbuclean's Status FINISHED.

    That is cleanup chatter, not a path being copied. A slash in
    /var/lib/mbu-gui/mount used to make the whole diagnostic look like a file.
    """
    junk = [
        "mbuclean mbuClean:1269 Status FINISHED and removed /var/lib/mbu-gui/mount OK",
        "mbuclean mbuClean:1270 Status You should be able to detach backup devices safely.",
        "\x1b[32mFINISHED\x1b[0m",
        "[4m[1mDO NOT FORGET to unplug",
        "DONE- BACKUP FROM main TO bak1 : efi root",
        "BACKING UP PARTITION SET main TO bak1",
    ]
    for line in junk:
        assert current_file_from_line(line) is None, line


def test_strip_ansi_removes_escapes_and_orphan_sgr():
    """MBU's pretty diagnostics leave [32mFINISHED when the ESC is lost."""
    assert strip_ansi("\x1b[32mFINISHED\x1b[0m") == "FINISHED"
    assert strip_ansi("[4m[1mDO NOT FORGET") == "DO NOT FORGET"
    assert strip_ansi("home/alex/.bashrc") == "home/alex/.bashrc"


def test_copied_bytes_come_from_rsync_total_size_lines():
    """rsync -v (MBU's default) prints 'total size is' after each partition."""
    lines = [
        "sent 1,234 bytes  received 56 bytes  78.00 bytes/sec",
        "total size is 12,884,901,888  speedup is 1.00",
        "total size is 1,073,741,824  speedup is 1.23",
    ]
    # 12 GiB + 1 GiB; never invent a number when the line is absent.
    assert copied_bytes_from_lines(lines) == 12_884_901_888 + 1_073_741_824
    assert copied_bytes_from_lines(["home/alex/.bashrc"]) is None


def test_backup_summary_uses_size_when_known_and_never_fakes_one():
    assert (
        backup_summary(from_set="main", to_set="backuptest", copied_bytes=12_884_901_888)
        == "Copied about 12 GB from this computer (main) onto backuptest."
    )
    assert (
        backup_summary(from_set="main", to_set="bak1", copied_bytes=None)
        == "Copied from this computer (main) onto bak1."
    )


def test_route_sets_are_read_from_mbu_backup_lines():
    assert route_sets_from_lines(["BACKING UP PARTITION SET main TO bak1"]) == (
        "main",
        "bak1",
    )
    assert route_sets_from_lines(
        ["2025/01/07-10:00:00 START BACKUP FROM main TO backuptest"]
    ) == ("main", "backuptest")
