"""Sidebar widget for meeting history browsing and search."""

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
    """A single clickable meeting entry in the sidebar."""

    clicked = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, meeting: Meeting, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meeting_id = meeting.id
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Top row: name + delete button
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self._name_label = QLabel(meeting.name or "Untitled Meeting")
        self._name_label.setObjectName("sidebarItemName")
        self._name_label.setWordWrap(True)
        top_row.addWidget(self._name_label, 1)

        self._delete_btn = QPushButton("\u00d7")
        self._delete_btn.setObjectName("sidebarDeleteBtn")
        self._delete_btn.setFixedSize(20, 20)
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._meeting_id)
        )
        top_row.addWidget(self._delete_btn)

        layout.addLayout(top_row)

        # Date + duration line
        date_str = meeting.created_at[:10] if meeting.created_at else ""
        duration_mins = (
            int(meeting.duration_secs) // 60 if meeting.duration_secs else 0
        )
        meta_text = date_str
        if duration_mins > 0:
            meta_text += f"  |  {duration_mins} min"
        meta_label = QLabel(meta_text)
        meta_label.setObjectName("sidebarItemMeta")
        layout.addWidget(meta_label)

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
    """Meeting history sidebar with search."""

    meeting_selected = Signal(int)
    meeting_deleted = Signal(int)
    new_meeting_requested = Signal()
    search_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("Meetings")
        header.setObjectName("sidebarHeader")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(40)
        layout.addWidget(header)

        # Search field
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search meetings...")
        self._search_input.setObjectName("sidebarSearch")
        self._search_input.textChanged.connect(self.search_changed.emit)
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(8, 4, 8, 4)
        search_layout.addWidget(self._search_input)
        layout.addWidget(search_container)

        # New Meeting button
        self._new_btn = QPushButton("+ New Meeting")
        self._new_btn.setObjectName("sidebarNewBtn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.clicked.connect(self.new_meeting_requested.emit)
        new_container = QWidget()
        new_layout = QVBoxLayout(new_container)
        new_layout.setContentsMargins(8, 4, 8, 4)
        new_layout.addWidget(self._new_btn)
        layout.addWidget(new_container)

        # Scrollable meeting list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setObjectName("sidebarScroll")

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
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
