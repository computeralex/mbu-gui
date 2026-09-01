# tests/test_packaging.py
from pathlib import Path

def test_policy_exec_path():
    text = Path("data/org.linuxbackupsoftware.mbu-gui.policy").read_text()
    assert "/usr/lib/mbu-gui/mbu-gui-helper" in text
    assert "allow_gui" in text


def test_control_depends():
    text = Path("packaging/debian/control").read_text()
    for dep in ["python3", "policykit-1", "rsync", "gdisk"]:
        assert dep in text
    assert "python3-pyside6" not in text


def test_readme_pip_uses_break_system_packages():
    text = Path("README.md").read_text()
    assert "pip3 install --user --break-system-packages PySide6" in text
    assert "pip3 install --user PySide6\n" not in text
    assert "PEP 668" in text
    assert "externally managed" in text.lower()


def test_package_ships_root_owned_state_dir():
    text = Path("packaging/Makefile").read_text()
    assert "$(DEST)/var/lib/mbu-gui" in text
    assert "--root-owner-group" in text


def test_launcher_catches_pyside_import_error():
    text = Path("scripts/mbu-gui").read_text()
    assert "ImportError" in text
    assert "missing_pyside" in text
