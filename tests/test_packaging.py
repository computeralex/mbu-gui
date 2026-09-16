# tests/test_packaging.py
from pathlib import Path

def test_policy_exec_path():
    text = Path("data/org.linuxbackupsoftware.mbu-gui.policy").read_text()
    assert "/usr/lib/mbu-gui/mbu-gui-helper" in text
    assert "allow_gui" in text


def test_control_depends():
    text = Path("packaging/debian/control").read_text()
    for dep in ["python3", "policykit-1", "rsync", "gdisk", "libxcb-cursor0"]:
        assert dep in text
    assert "python3-pyside6" not in text
    assert "0.1.0~alpha5" in text


def test_readme_has_uninstall():
    text = Path("README.md").read_text()
    assert "sudo apt remove mbu-gui" in text
    assert "~/.config/mbu-gui" in text


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


def test_install_script_allows_downgrades():
    text = Path("scripts/install-alpha.sh").read_text()
    assert "--allow-downgrades" in text
