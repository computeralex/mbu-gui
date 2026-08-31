# tests/test_paths.py
from pathlib import Path
from types import SimpleNamespace

from mbu_gui.paths import home_for_helper, resolve_paths


def test_resolve_paths_uses_explicit_home_and_mbu_dir(tmp_path):
    mbu = tmp_path / "mbu"
    home = tmp_path / "home"
    p = resolve_paths(home=home, mbu_dir=mbu)
    assert p.mbu_dir == mbu
    assert p.state_dir == home / ".local/share/mbu-gui"
    assert p.log_dir == p.state_dir / "log"
    assert p.out_dir == p.state_dir / "out"
    assert p.mount_dir == p.state_dir / "mount"
    assert p.master_log == p.log_dir / "mbu.log"
    assert p.backup_latest_log == p.log_dir / "mbup-latest.log"
    assert p.format_latest_log == p.log_dir / "mbuformat-latest.log"


def test_resolve_paths_honors_env_mbu_dir(tmp_path):
    mbu = tmp_path / "bundled"
    p = resolve_paths(home=tmp_path, environ={"MBU_GUI_MBU_DIR": str(mbu)})
    assert p.mbu_dir == mbu


def test_home_for_helper_uses_pkexec_uid():
    def getpwuid(uid):
        assert uid == 1000
        return SimpleNamespace(pw_dir="/home/axel")

    home = home_for_helper(environ={"PKEXEC_UID": "1000"}, getpwuid=getpwuid)
    assert home == Path("/home/axel")


def test_home_for_helper_falls_back_to_home_env(tmp_path):
    home = home_for_helper(environ={"HOME": str(tmp_path)}, getpwuid=lambda uid: (_ for _ in ()).throw(KeyError(uid)))
    assert home == tmp_path
