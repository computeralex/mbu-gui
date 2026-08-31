# tests/test_packaging.py
from pathlib import Path

def test_policy_exec_path():
    text = Path("data/org.linuxbackupsoftware.mbu-gui.policy").read_text()
    assert "/usr/lib/mbu-gui/mbu-gui-helper" in text
    assert "allow_gui" in text


def test_control_depends():
    text = Path("packaging/debian/control").read_text()
    for dep in ["python3-pyside6", "policykit-1", "rsync", "gdisk"]:
        assert dep in text
