from pathlib import Path

from mbu_gui.backup_prefs import load_backup_selection, prefs_dir, save_backup_selection


def test_prefs_dir_uses_xdg(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert prefs_dir() == tmp_path / "mbu-gui"


def test_round_trip(tmp_path: Path):
    save_backup_selection(
        "main", functions=["root", "home"], boot_fix=False, config_dir=tmp_path
    )
    loaded = load_backup_selection("main", config_dir=tmp_path)
    assert loaded == {"functions": ["root", "home"], "boot_fix": False}
    assert (tmp_path / "backup-selection-main.json").is_file()


def test_corrupt_returns_none(tmp_path: Path):
    (tmp_path / "backup-selection-main.json").write_text("{nope", encoding="utf-8")
    assert load_backup_selection("main", config_dir=tmp_path) is None


def test_missing_returns_none(tmp_path: Path):
    assert load_backup_selection("main", config_dir=tmp_path) is None
