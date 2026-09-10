import pytest

import mbu_gui.paths


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    """Keep every test out of the real /var/lib/mbu-gui.

    The helper creates and writes its state directory as root, so a test that
    picked up the production default could modify real system state.
    """
    monkeypatch.setattr(mbu_gui.paths, "STATE_DIR", tmp_path / "var-lib-mbu-gui")
