from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import subprocess


def run_streamed(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout,
    on_start: Callable[[int], None] | None = None,
) -> int:
    # Its own session, so the whole tree below MBU shares one process group and
    # a cancel can stop rsync rather than only the shell that launched it.
    with subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    ) as proc:
        if on_start is not None:
            on_start(proc.pid)
        assert proc.stdout is not None
        for line in proc.stdout:
            stdout.write(line)
            stdout.flush()
        return proc.wait()
