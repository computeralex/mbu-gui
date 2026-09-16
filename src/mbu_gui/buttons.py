"""Shared proceed / leave button styling for the GUI.

LTR convention: leave/cancel on the left (secondary), continue/apply on the
right (primary). No icons — labels carry the meaning.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton

# Restrained accent — readable on Winux/KDE dark chrome without looking playful.
_PRIMARY_SS = """
QPushButton {
    background-color: #3B82F6;
    color: #FFFFFF;
    border: 1px solid #2563EB;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2563EB;
}
QPushButton:pressed {
    background-color: #1D4ED8;
}
QPushButton:disabled {
    background-color: #475569;
    color: #CBD5E1;
    border-color: #475569;
}
"""

_SECONDARY_SS = """
QPushButton {
    background-color: transparent;
    color: palette(window-text);
    border: 1px solid palette(mid);
    border-radius: 4px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: palette(button);
}
QPushButton:pressed {
    background-color: palette(mid);
}
QPushButton:disabled {
    color: palette(mid);
    border-color: palette(mid);
}
"""


def style_primary(button: QPushButton) -> QPushButton:
    button.setStyleSheet(_PRIMARY_SS)
    button.setDefault(True)
    button.setAutoDefault(True)
    return button


def style_secondary(button: QPushButton) -> QPushButton:
    button.setStyleSheet(_SECONDARY_SS)
    button.setDefault(False)
    button.setAutoDefault(False)
    return button


def add_leave_proceed_row(
    layout: QHBoxLayout, leave: QPushButton, proceed: QPushButton
) -> None:
    """Cancel/leave on the left, primary proceed on the right."""
    style_secondary(leave)
    style_primary(proceed)
    layout.addWidget(leave)
    layout.addStretch(1)
    layout.addWidget(proceed)
