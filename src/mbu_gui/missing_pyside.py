from __future__ import annotations

from collections.abc import Callable
import shutil
import subprocess
import sys
from typing import Any


MISSING_PYSIDE6_MESSAGE = (
    "MBU Backup needs PySide6, which Ubuntu 24.04 does not package as python3-pyside6.\n"
    "Install it with:\n"
    "  pip3 install --user --break-system-packages PySide6\n"
    "(--break-system-packages is required because Ubuntu marks the system Python as "
    "externally managed / PEP 668.)"
)

_NOTIFY_TITLE = "MBU Backup"
_NOTIFY_TEXT = (
    "MBU Backup needs PySide6. Install with: "
    "pip3 install --user --break-system-packages PySide6"
)


def is_pyside6_import_error(exc: BaseException) -> bool:
    if not isinstance(exc, ImportError):
        return False
    text = str(exc)
    name = getattr(exc, "name", None) or ""
    return "PySide6" in text or "pyside6" in text.lower() or str(name).startswith("PySide6")


def report_missing_pyside6(
    *,
    file=None,
    which: Callable[[str], str | None] | None = None,
    run: Callable[..., Any] | None = None,
) -> int:
    file = sys.stderr if file is None else file
    print(MISSING_PYSIDE6_MESSAGE, file=file)
    _notify_missing_pyside6(
        which=shutil.which if which is None else which,
        run=subprocess.run if run is None else run,
    )
    return 1


def _notify_missing_pyside6(*, which, run) -> None:
    commands = (
        ["kdialog", "--error", _NOTIFY_TEXT],
        ["zenity", "--error", "--no-markup", "--text", _NOTIFY_TEXT],
        ["notify-send", _NOTIFY_TITLE, _NOTIFY_TEXT],
    )
    for argv in commands:
        if not which(argv[0]):
            continue
        try:
            run(argv, check=False, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            continue
        return


def handle_import_error(
    exc: BaseException,
    *,
    which: Callable[[str], str | None] | None = None,
    run: Callable[..., Any] | None = None,
) -> int:
    if is_pyside6_import_error(exc):
        return report_missing_pyside6(which=which, run=run)
    raise exc
