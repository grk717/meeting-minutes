"""Modern scrollable panel displaying live transcript segments.

Redesigned with speaker badges, timestamp chips, and better
visual hierarchy for readability.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class _TranscriptSegmentWidget(QWidget):
    """A single transcript segment with timestamp and optional speaker."""

    def __init__(
        self, text: str, timestamp: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)

        # Top row: timestamp (and speaker if embedded in text)
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)

        if timestamp:
            ts_label = QLabel(timestamp)
            ts_label.setObjectName("transcriptTimestamp")
            ts_label.setFixedWidth(42)
            meta_row.addWidget(ts_label)

        # Check if text starts with "Speaker N:" or a name followed by ":"
        speaker_name = ""
        display_text = text
        if ": " in text:
            potential_speaker = text[:text.index(": ")]
            # Heuristic: speaker labels are short (under 30 chars)
            if len(potential_speaker) < 30:
                speaker_name = potential_speaker
                display_text = text[text.index(": ") + 2:]

        if speaker_name:
            speaker_label = QLabel(speaker_name)
            speaker_label.setObjectName("transcriptSpeaker")
            meta_row.addWidget(speaker_label)

        meta_row.addStretch()

        if timestamp or speaker_name:
            layout.addLayout(meta_row)

        # Text content
        text_label = QLabel(display_text)
        text_label.setObjectName("transcriptSegment")
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        if timestamp:
            text_label.setContentsMargins(42, 0, 0, 0)
        layout.addWidget(text_label)


class TranscriptPanel(QWidget):
    """Displays transcript segments in a scrollable, styled container."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("transcriptPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Transcript")
        header.setObjectName("transcriptHeader")
        header_row.addWidget(header)
        header_row.addStretch()

        outer.addLayout(header_row)

        # Scrollable container
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setObjectName("transcriptScroll")
        self._scroll.setMinimumHeight(120)

        self._container = QWidget()
        self._items_layout = QVBoxLayout(self._container)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(2)
        self._items_layout.addStretch()

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll, 1)

        self._segments: list[str] = []
        self._raw_segments: list[tuple[str, str]] = []

        # Placeholder
        self._placeholder = QLabel(
            "Transcripts will appear here during recording..."
        )
        self._placeholder.setObjectName("summaryPlaceholder")
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._items_layout.insertWidget(0, self._placeholder)

    def add_segment(self, text: str, timestamp: str) -> None:
        """Add a transcript segment to the panel."""
        if self._placeholder.isVisible():
            self._placeholder.setVisible(False)

        formatted = f"[{timestamp}]  {text}"
        self._segments.append(formatted)
        self._raw_segments.append((timestamp, text))

        segment_widget = _TranscriptSegmentWidget(text, timestamp)

        # Insert before the stretch
        idx = self._items_layout.count() - 1
        self._items_layout.insertWidget(idx, segment_widget)

        # Auto-scroll to bottom
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self) -> None:
        """Remove all segments."""
        while self._items_layout.count() > 1:
            item = self._items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._segments.clear()
        self._raw_segments.clear()

        # Re-add placeholder
        self._placeholder = QLabel(
            "Transcripts will appear here during recording..."
        )
        self._placeholder.setObjectName("summaryPlaceholder")
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._items_layout.insertWidget(0, self._placeholder)

    def get_full_transcript(self) -> str:
        """Return all segments joined as plain text."""
        return "\n".join(self._segments)

    def get_raw_segments(self) -> list[tuple[str, str]]:
        """Return (timestamp, text) pairs for log formatting."""
        return list(self._raw_segments)
