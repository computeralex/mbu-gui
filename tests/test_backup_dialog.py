import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtWidgets import QApplication

from mbu_gui.backup_dialog import BackupDialog
from mbu_gui.backup_prefs import load_backup_selection, save_backup_selection
from mbu_gui.disks import load_lsblk

FIXTURES = Path(__file__).parent / "fixtures"
_app = None


def app():
    global _app
    _app = _app or QApplication.instance() or QApplication([])
    return _app


def _inv():
    return load_lsblk((FIXTURES / "lsblk_named.json").read_text())


def test_dialog_restores_saved_selection(tmp_path: Path):
    app()
    inv = _inv()
    assert inv.live_set == "main"
    save_backup_selection(
        "main",
        functions=["root", "home"],
        boot_fix=False,
        config_dir=tmp_path,
    )
    dialog = BackupDialog(inv, config_dir=tmp_path)
    assert dialog.bootFixCheck.isChecked() is False
    checked = {name for name, box in dialog._function_checks if box.isChecked()}
    assert checked == {"root", "home"}


def test_dialog_saves_on_accept(tmp_path: Path):
    app()
    inv = _inv()
    dialog = BackupDialog(inv, config_dir=tmp_path)
    for name, box in dialog._function_checks:
        box.setChecked(name in {"efi", "root"})
    dialog.bootFixCheck.setChecked(True)
    dialog.accept()
    loaded = load_backup_selection("main", config_dir=tmp_path)
    assert loaded == {"functions": ["efi", "root"], "boot_fix": True}


def test_ok_disabled_when_nothing_checked(tmp_path: Path):
    app()
    inv = _inv()
    dialog = BackupDialog(inv, config_dir=tmp_path)
    assert dialog.okButton.isEnabled()
    for _, box in dialog._function_checks:
        box.setChecked(False)
    assert not dialog.okButton.isEnabled()


def test_unknown_saved_functions_ignored(tmp_path: Path):
    app()
    inv = _inv()
    save_backup_selection(
        "main",
        functions=["root", "nosuch"],
        boot_fix=True,
        config_dir=tmp_path,
    )
    dialog = BackupDialog(inv, config_dir=tmp_path)
    checked = {name for name, box in dialog._function_checks if box.isChecked()}
    assert checked == {"root"}
