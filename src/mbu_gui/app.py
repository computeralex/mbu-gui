from __future__ import annotations

from PySide6.QtWidgets import QApplication


def create_app(argv: list[str] | None = None) -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([] if argv is None else argv)
