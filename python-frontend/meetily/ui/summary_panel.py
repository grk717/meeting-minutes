"""Panel displaying a meeting summary from the LLM."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SummaryPanel(QGroupBox):
    """Displays a generated meeting summary with a generate button."""

    generate_requested = Signal()  # emitted when user clicks Generate

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Summary", parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 8)
        layout.setSpacing(8)

        # Generate button
        self._generate_btn = QPushButton("Generate Summary")
        self._generate_btn.setObjectName("recordBtn")
        self._generate_btn.setMinimumHeight(36)
        self._generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._generate_btn.clicked.connect(self.generate_requested.emit)
        self._generate_btn.setEnabled(False)
        layout.addWidget(self._generate_btn)

        # Scrollable summary text
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._label.setContentsMargins(8, 8, 8, 8)

        self._scroll.setWidget(self._label)
        layout.addWidget(self._scroll, 1)

        self.clear()

    def set_generate_enabled(self, enabled: bool) -> None:
        """Enable or disable the generate button."""
        self._generate_btn.setEnabled(enabled)

    def set_summary(self, text: str) -> None:
        """Display the summary text."""
        self._generate_btn.setEnabled(True)
        self._generate_btn.setText("Generate Summary")
        self._label.setObjectName("")
        self._label.setText(text)
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)

    def set_loading(self) -> None:
        """Show loading indicator."""
        self._generate_btn.setEnabled(False)
        self._generate_btn.setText("Generating...")
        self._label.setObjectName("statusLabel")
        self._label.setText("Generating summary...")
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)

    def clear(self) -> None:
        """Reset to placeholder state."""
        self._generate_btn.setEnabled(False)
        self._generate_btn.setText("Generate Summary")
        self._label.setObjectName("statusLabel")
        self._label.setText("Record a meeting, then click Generate Summary.")
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)

    def get_summary(self) -> str:
        """Return the current summary text."""
        return self._label.text()
