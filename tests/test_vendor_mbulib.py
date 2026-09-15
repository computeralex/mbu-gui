from pathlib import Path

MBULIB = Path(__file__).resolve().parents[1] / "vendor" / "mbu" / "mbulib"


def test_mbupartsync_unmount_uses_bang():
    text = MBULIB.read_text(encoding="utf-8", errors="replace")
    marker = 'DONE Syncronizing FROM ($fromspec)'
    idx = text.index(marker)
    window = text[idx : idx + 400]
    assert "if ! mbuCleanMountPt" in window
    assert "Ted reported missing !" in window
