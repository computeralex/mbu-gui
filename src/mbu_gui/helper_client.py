from __future__ import annotations

from pathlib import Path
import os
import sys


HELPER_REL = "mbu-gui-helper"
HELPER_PATH = Path("/usr/lib/mbu-gui/mbu-gui-helper")


def pkexec_argv(helper_path: Path, helper_args: list[str]) -> list[str]:
    return ["pkexec", str(helper_path), *helper_args]


def direct_argv(helper_path: Path, helper_args: list[str]) -> list[str]:
    if helper_path == Path("-m"):
        return [sys.executable, "-m", "mbu_gui_helper", *helper_args]
    return [str(helper_path), *helper_args]


def failed_command_message(exit_code: int) -> str:
    return f"The backup command failed (exit {exit_code})."


def explain_helper_failure(
    exit_code: int,
    stderr: str,
    *,
    helper_exists: bool,
    pkexec_exists: bool,
) -> str:
    if not helper_exists:
        return (
            "MBU helper is not installed. Install the mbu-gui package so "
            "backups can run with administrator permission."
        )
    if not pkexec_exists:
        return "PolicyKit (pkexec) is not available. Install the mbu-gui package on Winux/Ubuntu."
    stderr_l = stderr.lower()
    if (
        "dismissed" in stderr_l
        or "request dismissed" in stderr_l
        or (exit_code in (126, 127) and "cancel" in stderr_l)
    ):
        return "Administrator permission was cancelled. Nothing was changed."
    return failed_command_message(exit_code)


def which_helper() -> Path | None:
    if os.access(HELPER_PATH, os.X_OK):
        return HELPER_PATH
    return None
