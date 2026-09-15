from pathlib import Path

from mbu_gui.version import __version__, read_mbu_release


def test_gui_version_is_alpha2():
    assert __version__ == "0.1.0-alpha.3"


def test_read_mbu_release_from_readme_marker(tmp_path: Path):
    (tmp_path / "mbu-README.txt").write_text(
        "# sample\n# MBU Release mbu-20251115\n", encoding="utf-8"
    )
    assert read_mbu_release(tmp_path) == "mbu-20251115"


def test_read_mbu_release_unknown_when_missing(tmp_path: Path):
    assert read_mbu_release(tmp_path) == "unknown"


def test_read_mbu_release_from_vendored_tree():
    mbu_dir = Path(__file__).resolve().parents[1] / "vendor" / "mbu"
    assert read_mbu_release(mbu_dir) == "mbu-20251115"
