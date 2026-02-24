"""Shared inline button style applied directly to QPushButton widgets.

Qt QSS global cascading is unreliable for QPushButton when QWidget rules
are also present. This module provides a single inline stylesheet string
that can be applied via setStyleSheet() on any button to guarantee
consistent rendering matching the "New Meeting" button look.
"""

# Matches #sidebarNewBtn exactly: dark fill, muted text, subtle border.
BUTTON_STYLE = """
QPushButton {
    background-color: #1a1a2e;
    color: #8080a0;
    border: 1px solid #2a2a42;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #222238;
    color: #b0b0c4;
    border-color: #3a3a58;
}
QPushButton:pressed {
    background-color: #13131f;
    color: #8080a0;
    border-color: #2a2a42;
}
QPushButton:disabled {
    background-color: #111120;
    color: #3a3a4e;
    border: 1px solid #1a1a2a;
}
"""

# Smaller variant for compact buttons (detail bar, speaker panel)
BUTTON_STYLE_SMALL = """
QPushButton {
    background-color: #1a1a2e;
    color: #8080a0;
    border: 1px solid #2a2a42;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #222238;
    color: #b0b0c4;
    border-color: #3a3a58;
}
QPushButton:pressed {
    background-color: #13131f;
    color: #8080a0;
    border-color: #2a2a42;
}
QPushButton:disabled {
    background-color: #111120;
    color: #3a3a4e;
    border: 1px solid #1a1a2a;
}
"""


def apply_button_style(btn, small: bool = False) -> None:
    """Apply the standard button style inline to a QPushButton."""
    btn.setStyleSheet(BUTTON_STYLE_SMALL if small else BUTTON_STYLE)
