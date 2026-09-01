from __future__ import annotations

from collections.abc import Callable, Mapping
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from mbu_gui.disks import parse_lsblk, split_mbu_label
from mbu_gui.machine import (
    MachineRecord,
    inversion_reason,
    live_disk_id,
    load_machine_record,
    record_for,
    record_path,
    save_machine_record,
)
from mbu_gui.paths import MbuPaths, resolve_paths
from mbu_gui_helper.commands import (
    format_disk_argv,
    format_table_argv,
    mbuclean_argv,
    mbumount_argv,
    mbup_argv,
    mbu_environ,
    sfdisk_label_argv,
)
from mbu_gui_helper.runner import run_streamed
from mbu_gui_helper.safety import (
    assert_label_targets_live,
    assert_not_system_disk,
    resolve_format_target,
)

LSBLK_ARGV = [
    "lsblk",
    "-J",
    "-o",
    "NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINT,PARTLABEL,PARTN,UUID,MODEL,SERIAL,WWN,PTUUID",
]

state_symlink_error = "Refusing to use a state path that is not a plain root-owned directory"


class ArgumentParser(argparse.ArgumentParser):
    """Treat unknown single-dash tokens as values so --fselection -bootfix,... works."""

    def _parse_optional(self, arg_string):
        if (
            arg_string
            and arg_string[0] in self.prefix_chars
            and arg_string not in self._option_string_actions
            and not arg_string.startswith("--")
        ):
            return None
        return super()._parse_optional(arg_string)


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="mbu-gui-helper")
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup")
    backup.add_argument("--fselection", required=True)

    sub.add_parser("clean")

    mount = sub.add_parser("mount")
    mount.add_argument("--set", required=True, dest="set_name")

    sub.add_parser("write-format-table")

    fmt = sub.add_parser("format-disk")
    fmt.add_argument("--disk", required=True)
    fmt.add_argument("--disk-id", required=True, dest="disk_id")
    fmt.add_argument("--pset", required=True)

    label = sub.add_parser("label-live")
    label.add_argument("--labels", required=True)

    return parser


def _parse_labels(spec: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid label spec: {item}")
        name, label = item.split("=", 1)
        name = name.strip()
        label = label.strip()
        if not name or not label:
            raise ValueError(f"Invalid label spec: {item}")
        pairs.append((name, label))
    return pairs


def _load_inventory(lsblk_data: dict | None, environ: Mapping[str, str]):
    if lsblk_data is None:
        raw = subprocess.check_output(LSBLK_ARGV, text=True, env=dict(environ))
        lsblk_data = json.loads(raw)
    return parse_lsblk(lsblk_data)


def _make_state_dir(path: Path, *, parents: bool) -> None:
    """Create one state directory, refusing to write through a symlink.

    Running as root, a symlinked component would let the caller aim MBU's log
    and format-table writes at any path on the system.
    """
    if path.is_symlink():
        raise ValueError(f"{state_symlink_error}: {path}")
    path.mkdir(mode=0o755, parents=parents, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{state_symlink_error}: {path}")


def prepare_state_dirs(paths: MbuPaths) -> None:
    _make_state_dir(paths.state_dir, parents=True)
    for directory in (paths.log_dir, paths.out_dir, paths.mount_dir):
        _make_state_dir(directory, parents=False)


def record_labelled_machine(paths: MbuPaths, planned, inventory) -> None:
    """Setup just named this computer's partitions, so record the set it chose."""
    for _part, label in planned:
        parsed = split_mbu_label(label)
        if parsed is not None:
            save_machine_record(
                record_path(paths.state_dir),
                MachineRecord(machine_set=parsed[0], disk_id=live_disk_id(inventory)),
            )
            return


def assert_not_running_from_backup(paths: MbuPaths, inventory) -> None:
    """Refuse to back up when the running system is not the recorded machine.

    Recorded on the first backup, when the running root is necessarily the
    real machine: a clone cannot exist before one has been made.
    """
    path = record_path(paths.state_dir)
    record = load_machine_record(path)
    reason = inversion_reason(record, inventory)
    if reason is not None:
        raise ValueError(reason)
    if record is None:
        first = record_for(inventory)
        if first is not None:
            save_machine_record(path, first)


def mark_backup_started(paths: MbuPaths) -> None:
    """Record that a backup is under way before MBU can clone any UUID.

    MBU copies filesystem UUIDs partition by partition, so a run that dies
    part way through can leave the backup disk sharing UUIDs with this
    computer. The marker outlives a crashed helper or a killed GUI.
    """
    marker = paths.incomplete_marker
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        raise ValueError(f"{state_symlink_error}: {marker}")
    marker.write_text("a backup started and has not finished cleanly\n")


def format_table_path(paths: MbuPaths) -> Path:
    """Path MBU writes the generated format table to, cleared before each use.

    Root both writes and then reads this file, so we start from a known state
    instead of trusting whatever is already sitting there.
    """
    table = paths.out_dir / "mbuformat.table"
    if table.is_symlink() or (table.exists() and not table.is_file()):
        raise ValueError(f"{state_symlink_error}: {table}")
    table.unlink(missing_ok=True)
    return table


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    lsblk_data: dict | None = None,
    run: Callable | None = None,
    state_dir: Path | None = None,
) -> int:
    environ = os.environ if environ is None else environ
    paths = resolve_paths(state_dir=state_dir, environ=environ)
    args = _build_parser().parse_args(argv)
    run = run_streamed if run is None else run
    env = mbu_environ(paths, environ)
    # Logs and mount points live under root-owned state; keep them readable so
    # the unprivileged GUI can show progress without any chown into $HOME.
    os.umask(0o022)
    try:
        prepare_state_dirs(paths)
        return _dispatch(
            args,
            paths=paths,
            env=env,
            lsblk_data=lsblk_data,
            environ=environ,
            run=run,
        )
    except ValueError as e:
        print(e)
        return 2


def _dispatch(args, *, paths, env, lsblk_data, environ, run) -> int:
    stdout = sys.stdout

    def invoke(argv: list[str]) -> int:
        return run(argv, cwd=paths.mbu_dir, env=env, stdout=stdout)

    inventory = _load_inventory(lsblk_data, environ)

    def then_clean(primary: int) -> int:
        clean = invoke(mbuclean_argv())
        return primary if primary != 0 else clean

    if args.command == "backup":
        assert_not_running_from_backup(paths, inventory)
        mark_backup_started(paths)
        code = then_clean(invoke(mbup_argv(args.fselection)))
        if code == 0:
            paths.incomplete_marker.unlink(missing_ok=True)
        return code

    if args.command == "clean":
        return invoke(mbuclean_argv())

    if args.command == "mount":
        return invoke(mbumount_argv(args.set_name))

    if args.command == "write-format-table":
        return invoke(format_table_argv())

    if args.command == "format-disk":
        target = resolve_format_target(args.disk_id, args.disk, inventory)
        assert_not_system_disk(target, inventory)
        tablefile = format_table_path(paths)
        table_code = invoke(format_table_argv())
        format_code = 0
        if table_code == 0:
            format_code = invoke(format_disk_argv(target, args.pset, str(tablefile)))
        primary = table_code if table_code != 0 else format_code
        return then_clean(primary)

    if args.command == "label-live":
        planned = []
        for name, label in _parse_labels(args.labels):
            part = assert_label_targets_live(name, inventory)
            if part.partn is None:
                raise ValueError(f"Partition {name} has no partition number")
            planned.append((part, label))
        for part, label in planned:
            code = invoke(sfdisk_label_argv(part.disk, part.partn, label))
            if code != 0:
                return code
        record_labelled_machine(paths, planned, inventory)
        return 0

    raise ValueError(f"Unknown command: {args.command}")
