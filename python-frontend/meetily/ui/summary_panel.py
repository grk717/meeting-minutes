"""Modern panel displaying a meeting summary from the LLM.

Redesigned with document-like rendering, proper section header,
and polished generate button.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SummaryPanel(QWidget):
    """Displays a generated meeting summary with a generate button."""

    generate_requested = Signal()  # emitted when user clicks Generate

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("summaryPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # Header row with title and generate button
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(12)

        header = QLabel("Summary")
        header.setObjectName("summaryHeader")
        header_row.addWidget(header)
        header_row.addStretch()

        self._generate_btn = QPushButton("Generate")
        self._generate_btn.setObjectName("generateBtn")
        self._generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._generate_btn.clicked.connect(self.generate_requested.emit)
        self._generate_btn.setEnabled(False)
        header_row.addWidget(self._generate_btn)

        outer.addLayout(header_row)

        # Scrollable summary text
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setObjectName("summaryScroll")

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._label.setContentsMargins(0, 0, 0, 0)

        self._scroll.setWidget(self._label)
        outer.addWidget(self._scroll, 1)

        self.clear()

    def set_generate_enabled(self, enabled: bool) -> None:
        """Enable or disable the generate button."""
        self._generate_btn.setEnabled(enabled)

    def set_summary(self, text: str) -> None:
        """Display the summary text."""
        self._generate_btn.setEnabled(True)
        self._generate_btn.setText("Generate")
        self._label.setObjectName("summaryText")
        self._label.setText(text)
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)

    def set_loading(self) -> None:
        """Show loading indicator."""
        self._generate_btn.setEnabled(False)
        self._generate_btn.setText("Generating...")
        self._label.setObjectName("summaryPlaceholder")
        self._label.setText("Generating summary...")
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)

    def clear(self) -> None:
        """Reset to placeholder state."""
        self._generate_btn.setEnabled(False)
        self._generate_btn.setText("Generate")
        self._label.setObjectName("summaryPlaceholder")
        self._label.setText(
            "Record a meeting, then generate a summary."
        )
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)

    def get_summary(self) -> str:
        """Return the current summary text."""
        return self._label.text()
