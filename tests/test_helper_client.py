from pathlib import Path
from mbu_gui.helper_client import (
    explain_helper_failure,
    failed_command_message,
    pkexec_argv,
)


def test_pkexec_argv():
    assert pkexec_argv(Path("/usr/lib/mbu-gui/mbu-gui-helper"), ["backup", "--fselection", "root"]) == [
        "pkexec", "/usr/lib/mbu-gui/mbu-gui-helper", "backup", "--fselection", "root",
    ]


def test_messages():
    assert "not installed" in explain_helper_failure(127, "", helper_exists=False, pkexec_exists=True)
    assert "pkexec" in explain_helper_failure(127, "", helper_exists=True, pkexec_exists=False).lower()
    assert "cancelled" in explain_helper_failure(126, "Error executing command as another user: Request dismissed", helper_exists=True, pkexec_exists=True).lower()
    assert failed_command_message(1) == "The backup command failed (exit 1)."
