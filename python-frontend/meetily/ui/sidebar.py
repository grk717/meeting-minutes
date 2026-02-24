"""Modern sidebar widget for meeting history browsing and search.

Redesigned with card-style meeting items, better visual hierarchy,
and polished interactions.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from meetily.storage.database import Meeting

log = logging.getLogger(__name__)


class MeetingListItem(QWidget):
    """A single clickable meeting card in the sidebar."""

    clicked = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, meeting: Meeting, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meeting_id = meeting.id
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Top row: name + delete button
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self._name_label = QLabel(meeting.name or "Untitled Meeting")
        self._name_label.setObjectName("sidebarItemName")
        self._name_label.setWordWrap(False)
        # Elide long names
        self._name_label.setMaximumWidth(180)
        top_row.addWidget(self._name_label, 1)

        self._delete_btn = QPushButton("\u00d7")
        self._delete_btn.setObjectName("sidebarDeleteBtn")
        self._delete_btn.setFixedSize(22, 22)
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._meeting_id)
        )
        top_row.addWidget(self._delete_btn)

        layout.addLayout(top_row)

        # Meta line: date + duration
        date_str = meeting.created_at[:10] if meeting.created_at else ""
        duration_mins = (
            int(meeting.duration_secs) // 60 if meeting.duration_secs else 0
        )
        meta_parts = []
        if date_str:
            meta_parts.append(date_str)
        if duration_mins > 0:
            meta_parts.append(f"{duration_mins}m")
        # Add summary indicator
        if meeting.summary_text:
            meta_parts.append("Summarized")

        meta_label = QLabel("  \u00b7  ".join(meta_parts))
        meta_label.setObjectName("sidebarItemMeta")
        layout.addWidget(meta_label)

        # Transcript preview (first 60 chars)
        preview_text = ""
        if meeting.transcript_text:
            # Get first meaningful line
            lines = [l.strip() for l in meeting.transcript_text.split("\n") if l.strip()]
            if lines:
                raw = lines[0]
                # Strip timestamp prefix if present
                if raw.startswith("[") and "]" in raw:
                    raw = raw[raw.index("]") + 1:].strip()
                preview_text = raw[:65]
                if len(raw) > 65:
                    preview_text += "..."

        if preview_text:
            preview_label = QLabel(preview_text)
            preview_label.setObjectName("sidebarItemPreview")
            preview_label.setWordWrap(False)
            layout.addWidget(preview_label)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, event) -> None:
        self._delete_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._delete_btn.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._meeting_id)
        super().mousePressEvent(event)


class Sidebar(QWidget):
    """Meeting history sidebar with search and new meeting action."""

    meeting_selected = Signal(int)
    meeting_deleted = Signal(int)
    new_meeting_requested = Signal()
    search_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top section with title and new button ──
        top_section = QWidget()
        top_layout = QVBoxLayout(top_section)
        top_layout.setContentsMargins(16, 16, 16, 12)
        top_layout.setSpacing(12)

        # Title row
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Meetings")
        title.setObjectName("sidebarTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        top_layout.addLayout(title_row)

        # Search field with icon hint
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search...")
        self._search_input.setObjectName("sidebarSearch")
        self._search_input.textChanged.connect(self.search_changed.emit)
        top_layout.addWidget(self._search_input)

        # New Meeting button
        self._new_btn = QPushButton("+ New Meeting")
        self._new_btn.setObjectName("sidebarNewBtn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.clicked.connect(self.new_meeting_requested.emit)
        top_layout.addWidget(self._new_btn)

        layout.addWidget(top_section)

        # Subtle divider
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setObjectName("divider")
        layout.addWidget(divider)

        # ── Scrollable meeting list ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setObjectName("sidebarScroll")

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

        self._items: list[MeetingListItem] = []
        self._selected_id: int | None = None

    def populate(self, meetings: list[Meeting]) -> None:
        """Rebuild the meeting list from a list of Meeting objects."""
        self._list_container.setUpdatesEnabled(False)

        for item in self._items:
            item.deleteLater()
        self._items.clear()

        # Clear layout except trailing stretch
        while self._list_layout.count() > 1:
            child = self._list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for meeting in meetings:
            item = MeetingListItem(meeting)
            item.clicked.connect(self._on_item_clicked)
            item.delete_requested.connect(self.meeting_deleted.emit)
            if meeting.id == self._selected_id:
                item.set_selected(True)
            idx = self._list_layout.count() - 1  # before stretch
            self._list_layout.insertWidget(idx, item)
            self._items.append(item)

        self._list_container.setUpdatesEnabled(True)

    def set_selected(self, meeting_id: int | None) -> None:
        self._selected_id = meeting_id
        for item in self._items:
            item.set_selected(item._meeting_id == meeting_id)

    @property
    def search_query(self) -> str:
        return self._search_input.text().strip()

    def _on_item_clicked(self, meeting_id: int) -> None:
        self.set_selected(meeting_id)
        self.meeting_selected.emit(meeting_id)
