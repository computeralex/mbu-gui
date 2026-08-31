from __future__ import annotations

from pathlib import Path
import subprocess


def run_streamed(argv: list[str], *, cwd: Path, env: dict[str, str], stdout) -> int:
    with subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            stdout.write(line)
            stdout.flush()
        return proc.wait()
