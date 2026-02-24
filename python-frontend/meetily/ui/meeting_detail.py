"""Meeting detail bar with back navigation and copy/export actions.

Redesigned with cleaner action buttons and better visual hierarchy.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from meetily.storage.database import Meeting
from meetily.ui.button_style import apply_button_style


class MeetingDetailBar(QWidget):
    """Bar shown above transcript/summary when viewing a stored meeting."""

    back_requested = Signal()
    retranscribe_requested = Signal()
    copy_requested = Signal()
    export_txt_requested = Signal()
    export_md_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("meetingDetailBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Back button
        self._back_btn = QPushButton("\u2190 Back")
        self._back_btn.setObjectName("detailActionBtn")
        apply_button_style(self._back_btn, small=True)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setFixedWidth(70)
        self._back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(self._back_btn)

        # Title + meta
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(1)

        self._title_label = QLabel("")
        self._title_label.setObjectName("meetingDetailTitle")
        info_col.addWidget(self._title_label)

        self._meta_label = QLabel("")
        self._meta_label.setObjectName("meetingDetailMeta")
        info_col.addWidget(self._meta_label)

        layout.addLayout(info_col, 1)

        # Action buttons
        self._retranscribe_btn = QPushButton("Retranscribe")
        self._retranscribe_btn.setObjectName("detailPrimaryBtn")
        apply_button_style(self._retranscribe_btn, small=True)
        self._retranscribe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retranscribe_btn.clicked.connect(self.retranscribe_requested.emit)
        layout.addWidget(self._retranscribe_btn)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("detailActionBtn")
        apply_button_style(self._copy_btn, small=True)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self.copy_requested.emit)
        layout.addWidget(self._copy_btn)

        self._export_txt_btn = QPushButton(".txt")
        self._export_txt_btn.setObjectName("detailActionBtn")
        apply_button_style(self._export_txt_btn, small=True)
        self._export_txt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_txt_btn.clicked.connect(self.export_txt_requested.emit)
        layout.addWidget(self._export_txt_btn)

        self._export_md_btn = QPushButton(".md")
        self._export_md_btn.setObjectName("detailActionBtn")
        apply_button_style(self._export_md_btn, small=True)
        self._export_md_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_md_btn.clicked.connect(self.export_md_requested.emit)
        layout.addWidget(self._export_md_btn)

    def set_meeting(self, meeting: Meeting) -> None:
        self._title_label.setText(meeting.name or "Untitled Meeting")

        meta_parts = []
        if meeting.created_at:
            meta_parts.append(meeting.created_at[:10])
        if meeting.duration_secs:
            mins = int(meeting.duration_secs) // 60
            secs = int(meeting.duration_secs) % 60
            if mins > 0:
                meta_parts.append(f"{mins}m {secs}s")
            else:
                meta_parts.append(f"{secs}s")
        self._meta_label.setText("  \u00b7  ".join(meta_parts))

        # Only enable retranscribe if there's a WAV file
        self._retranscribe_btn.setEnabled(bool(meeting.wav_path))
