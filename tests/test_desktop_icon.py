# tests/test_desktop_icon.py
from pathlib import Path
from mbu_gui.desktop_icon import maybe_install_desktop_icon

def test_copies_once(tmp_path):
    desk = tmp_path / "Desktop"
    desk.mkdir()
    src = tmp_path / "src.desktop"
    src.write_text("hello")
    maybe_install_desktop_icon(desktop_dir=desk, source=src)
    dest = desk / "mbu-gui.desktop"
    assert dest.read_text() == "hello"
    dest.write_text("keep")
    maybe_install_desktop_icon(desktop_dir=desk, source=src)
    assert dest.read_text() == "keep"


def test_missing_desktop_dir(tmp_path):
    src = tmp_path / "src.desktop"
    src.write_text("hello")
    maybe_install_desktop_icon(desktop_dir=tmp_path / "nope", source=src)


def test_desktop_file_has_absolute_exec():
    text = Path("data/mbu-gui.desktop").read_text()
    assert "Exec=/usr/bin/mbu-gui" in text
    assert "Terminal=false" in text
    assert "Path=" not in text


def test_oserror_swallowed(tmp_path):
    desk = tmp_path / "Desktop"
    desk.mkdir()
    src = tmp_path / "missing.desktop"
    maybe_install_desktop_icon(desktop_dir=desk, source=src)
    assert not (desk / "mbu-gui.desktop").exists()
