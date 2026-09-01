from __future__ import annotations

from collections.abc import Callable, Mapping
import argparse
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path

from mbu_gui.disks import parse_lsblk
from mbu_gui.paths import MbuPaths, home_for_helper, resolve_paths
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
    assert_not_live_disk,
    resolve_format_target,
)

LSBLK_ARGV = [
    "lsblk",
    "-J",
    "-o",
    "NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINT,PARTLABEL,PARTN,UUID,MODEL,SERIAL,WWN,PTUUID",
]


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


def _pkexec_ids(environ: Mapping[str, str]) -> tuple[int, int] | None:
    uid_s = environ.get("PKEXEC_UID")
    if not uid_s:
        return None
    try:
        uid = int(uid_s)
    except ValueError:
        return None
    try:
        gid = pwd.getpwuid(uid).pw_gid
    except (KeyError, TypeError, OverflowError, AttributeError):
        gid = uid
    return uid, gid


def _chown(path: Path, uid: int, gid: int) -> None:
    try:
        os.chown(path, uid, gid, follow_symlinks=False)
    except (OSError, TypeError):
        # Python <3.13 os.chown may not take follow_symlinks on all platforms.
        try:
            os.chown(path, uid, gid)
        except OSError:
            return


def chown_state_to_pkexec_uid(paths: MbuPaths, environ: Mapping[str, str]) -> None:
    """Chown helper state dirs so the GUI user can read logs.

    Never recurse into mount_dir: that directory holds mounted backup
    filesystems (and possibly a symlink to /).
    """
    ids = _pkexec_ids(environ)
    if ids is None:
        return
    uid, gid = ids
    targets = [
        paths.state_dir,
        paths.log_dir,
        paths.out_dir,
        paths.mount_dir,
    ]
    for directory in (paths.log_dir, paths.out_dir):
        if directory.is_dir():
            for child in directory.iterdir():
                if child.is_symlink():
                    continue
                if child.is_file():
                    targets.append(child)
    for path in targets:
        if path.exists() or path.is_symlink():
            _chown(path, uid, gid)


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    lsblk_data: dict | None = None,
    run: Callable | None = None,
) -> int:
    environ = os.environ if environ is None else environ
    home = home_for_helper(environ=environ)
    paths = resolve_paths(home=home, environ=environ)
    args = _build_parser().parse_args(argv)
    run = run_streamed if run is None else run
    env = mbu_environ(paths, environ)
    for directory in (paths.log_dir, paths.out_dir, paths.mount_dir):
        directory.mkdir(parents=True, exist_ok=True)
    chown_state_to_pkexec_uid(paths, environ)
    try:
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
    finally:
        chown_state_to_pkexec_uid(paths, environ)


def _dispatch(args, *, paths, env, lsblk_data, environ, run) -> int:
    stdout = sys.stdout

    def invoke(argv: list[str]) -> int:
        return run(argv, cwd=paths.mbu_dir, env=env, stdout=stdout)

    inventory = _load_inventory(lsblk_data, environ)

    def then_clean(primary: int) -> int:
        clean = invoke(mbuclean_argv())
        return primary if primary != 0 else clean

    if args.command == "backup":
        return then_clean(invoke(mbup_argv(args.fselection)))

    if args.command == "clean":
        return invoke(mbuclean_argv())

    if args.command == "mount":
        return invoke(mbumount_argv(args.set_name))

    if args.command == "write-format-table":
        return invoke(format_table_argv())

    if args.command == "format-disk":
        target = resolve_format_target(args.disk_id, args.disk, inventory)
        assert_not_live_disk(target, inventory)
        table_code = invoke(format_table_argv())
        format_code = 0
        if table_code == 0:
            tablefile = str(paths.out_dir / "mbuformat.table")
            format_code = invoke(format_disk_argv(target, args.pset, tablefile))
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
        return 0

    raise ValueError(f"Unknown command: {args.command}")
