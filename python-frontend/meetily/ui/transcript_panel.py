"""Scrollable panel displaying live transcript segments."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class TranscriptPanel(QGroupBox):
    """Displays transcript segments in a scrollable list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Transcript", parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 8)

        # Scrollable container
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMinimumHeight(120)

        self._container = QWidget()
        self._items_layout = QVBoxLayout(self._container)
        self._items_layout.setContentsMargins(4, 4, 4, 4)
        self._items_layout.setSpacing(6)
        self._items_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

        self._segments: list[str] = []

        # Placeholder
        self._placeholder = QLabel("Transcripts will appear here during recording...")
        self._placeholder.setObjectName("statusLabel")
        self._placeholder.setWordWrap(True)
        self._items_layout.insertWidget(0, self._placeholder)

    def add_segment(self, text: str, timestamp: str) -> None:
        """Add a transcript segment to the panel."""
        # Hide placeholder on first segment
        if self._placeholder.isVisible():
            self._placeholder.setVisible(False)

        formatted = f"[{timestamp}]  {text}"
        self._segments.append(formatted)

        label = QLabel(formatted)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setObjectName("transcriptSegment")

        # Insert before the stretch
        idx = self._items_layout.count() - 1
        self._items_layout.insertWidget(idx, label)

        # Auto-scroll to bottom
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self) -> None:
        """Remove all segments."""
        # Remove all widgets except the stretch
        while self._items_layout.count() > 1:
            item = self._items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._segments.clear()

        # Re-add placeholder
        self._placeholder = QLabel("Transcripts will appear here during recording...")
        self._placeholder.setObjectName("statusLabel")
        self._placeholder.setWordWrap(True)
        self._items_layout.insertWidget(0, self._placeholder)

    def get_full_transcript(self) -> str:
        """Return all segments joined as plain text."""
        return "\n".join(self._segments)
