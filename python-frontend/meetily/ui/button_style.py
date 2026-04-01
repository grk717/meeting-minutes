"""Shared inline button style applied directly to QPushButton widgets.

Qt QSS global cascading is unreliable for QPushButton when QWidget rules
are also present. This module provides a single inline stylesheet string
that can be applied via setStyleSheet() on any button to guarantee
consistent rendering matching the "New Meeting" button look.
"""

# Matches #sidebarNewBtn exactly: dark fill, muted text, subtle border.
BUTTON_STYLE = """
QPushButton {
    background-color: #141e2e;
    color: #6e8494;
    border: 1px solid #1e3040;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #1c2a38;
    color: #a0b4c4;
    border-color: #284058;
}
QPushButton:pressed {
    background-color: #0e1620;
    color: #6e8494;
    border-color: #1e3040;
}
QPushButton:disabled {
    background-color: #0e1822;
    color: #2e4050;
    border: 1px solid #141e2a;
}
"""

# Smaller variant for compact buttons (detail bar, speaker panel)
BUTTON_STYLE_SMALL = """
QPushButton {
    background-color: #141e2e;
    color: #6e8494;
    border: 1px solid #1e3040;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #1c2a38;
    color: #a0b4c4;
    border-color: #284058;
}
QPushButton:pressed {
    background-color: #0e1620;
    color: #6e8494;
    border-color: #1e3040;
}
QPushButton:disabled {
    background-color: #0e1822;
    color: #2e4050;
    border: 1px solid #141e2a;
}
"""


def apply_button_style(btn, small: bool = False) -> None:
    """Apply the standard button style inline to a QPushButton."""
    btn.setStyleSheet(BUTTON_STYLE_SMALL if small else BUTTON_STYLE)
