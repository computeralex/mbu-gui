from __future__ import annotations

from collections.abc import Mapping

from mbu_gui.paths import MbuPaths
from mbu_gui_helper.safety import normalize_disk


def mbup_argv(fselection: str) -> list[str]:
    return ["./mbup", "ask=n", f"fselection={fselection}"]


def mbuclean_argv() -> list[str]:
    return ["./mbuclean"]


def mbumount_argv(set_name: str) -> list[str]:
    return ["./mbumount", set_name]


def format_table_argv() -> list[str]:
    return ["./mbulib", "mbuFormatTableWrite"]


def format_disk_argv(disk: str, pset: str, tablefile: str) -> list[str]:
    return [
        "./mbulib",
        "mbuFormatDisk",
        "fake=n",
        f"disk={normalize_disk(disk)}",
        f"pset={pset}",
        f"tablefile={tablefile}",
    ]


def sfdisk_label_argv(disk: str, partn: int, label: str) -> list[str]:
    return [
        "sfdisk",
        "--part-label",
        f"/dev/{normalize_disk(disk)}",
        str(partn),
        label,
    ]


def partx_update_argv(disk: str) -> list[str]:
    """Nudge the kernel to re-read one disk's partition entries.

    sfdisk cannot make the kernel re-read the table of the disk it is running
    from, so partx updates the entries in place and the resulting uevents make
    udev re-probe the new names.
    """
    return ["partx", "-u", f"/dev/{normalize_disk(disk)}"]


def udev_settle_argv() -> list[str]:
    return ["udevadm", "settle"]


def mbu_environ(paths: MbuPaths, base: Mapping[str, str]) -> dict[str, str]:
    env = dict(base)
    env["mbuDir"] = str(paths.mbu_dir)
    env["mbuLogDir"] = str(paths.log_dir)
    env["mbuMountDir"] = str(paths.mount_dir)
    env["mbuOutDir"] = str(paths.out_dir)
    env["mbuMasterLogFile"] = str(paths.master_log)
    env["mbuBackupLatestLogFile"] = str(paths.backup_latest_log)
    env["mbuFormatLatestLogFile"] = str(paths.format_latest_log)
    env["mbuDoRsyncVerbose"] = "y"
    return env
