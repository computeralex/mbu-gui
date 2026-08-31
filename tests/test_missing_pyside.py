from types import SimpleNamespace

from mbu_gui.missing_pyside import (
    MISSING_PYSIDE6_MESSAGE,
    handle_import_error,
    is_pyside6_import_error,
    report_missing_pyside6,
)


def test_is_pyside6_import_error():
    assert is_pyside6_import_error(ImportError("No module named 'PySide6'"))
    assert is_pyside6_import_error(ImportError("No module named 'PySide6.QtWidgets'"))
    assert is_pyside6_import_error(ModuleNotFoundError("No module named 'PySide6'"))
    assert not is_pyside6_import_error(ImportError("No module named 'mbu_gui.logs'"))
    assert not is_pyside6_import_error(ImportError("No module named 'foo'"))


def test_report_missing_pyside6_prints_and_tries_kdialog(capsys):
    calls = []

    def which(name):
        return "/usr/bin/kdialog" if name == "kdialog" else None

    def run(argv, **kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0)

    code = report_missing_pyside6(which=which, run=run)
    assert code == 1
    err = capsys.readouterr().err
    assert "PySide6" in err
    assert "--break-system-packages" in err
    assert err.strip() == MISSING_PYSIDE6_MESSAGE.strip()
    assert calls[0][0] == "kdialog"


def test_report_missing_pyside6_falls_back_to_zenity_then_notify(capsys):
    calls = []

    def which(name):
        return "/usr/bin/" + name if name in {"zenity", "notify-send"} else None

    def run(argv, **kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0)

    assert report_missing_pyside6(which=which, run=run) == 1
    assert calls[0][0] == "zenity"
    calls.clear()

    def which_notify(name):
        return "/usr/bin/notify-send" if name == "notify-send" else None

    assert report_missing_pyside6(which=which_notify, run=run) == 1
    assert calls[0][0] == "notify-send"


def test_handle_import_error_reports_pyside(capsys):
    calls = []
    code = handle_import_error(
        ImportError("No module named 'PySide6'"),
        which=lambda name: None,
        run=lambda *a, **k: calls.append(a),
    )
    assert code == 1
    assert "PySide6" in capsys.readouterr().err
    assert calls == []


def test_handle_import_error_reraises_other():
    try:
        handle_import_error(ImportError("No module named 'foo'"))
        assert False, "expected ImportError"
    except ImportError as e:
        assert "foo" in str(e)
