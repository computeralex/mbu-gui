# tests/test_paths.py
from pathlib import Path

import mbu_gui.paths
from mbu_gui.paths import STATE_DIR, resolve_paths


def test_state_dir_is_root_owned_and_not_under_a_home():
    # STATE_DIR here is the import-time constant; conftest patches the module
    # attribute that resolve_paths reads, so assert on both.
    assert STATE_DIR == Path("/var/lib/mbu-gui")
    assert ".local" not in str(STATE_DIR)
    p = resolve_paths(environ={})
    assert p.state_dir == mbu_gui.paths.STATE_DIR


def test_resolve_paths_uses_explicit_state_dir_and_mbu_dir(tmp_path):
    mbu = tmp_path / "mbu"
    state = tmp_path / "state"
    p = resolve_paths(state_dir=state, mbu_dir=mbu)
    assert p.mbu_dir == mbu
    assert p.state_dir == state
    assert p.log_dir == p.state_dir / "log"
    assert p.out_dir == p.state_dir / "out"
    assert p.mount_dir == p.state_dir / "mount"
    assert p.master_log == p.log_dir / "mbu.log"
    assert p.backup_latest_log == p.log_dir / "mbup-latest.log"
    assert p.format_latest_log == p.log_dir / "mbuformat-latest.log"


def test_resolve_paths_honors_env_mbu_dir(tmp_path):
    mbu = tmp_path / "bundled"
    p = resolve_paths(environ={"MBU_GUI_MBU_DIR": str(mbu)})
    assert p.mbu_dir == mbu


def test_state_dir_ignores_home_environment(tmp_path):
    """HOME and PKEXEC_UID must not be able to move root's state directory."""
    p = resolve_paths(environ={"HOME": "/home/attacker", "PKEXEC_UID": "1000"})
    assert p.state_dir == mbu_gui.paths.STATE_DIR
    assert "/home/attacker" not in str(p.state_dir)
