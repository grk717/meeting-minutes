"""Meeting detail bar with back navigation and copy/export actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from meetily.storage.database import Meeting


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
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._back_btn = QPushButton("\u2190 Back")
        self._back_btn.setObjectName("pauseBtn")
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setFixedWidth(70)
        self._back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(self._back_btn)

        self._title_label = QLabel("")
        self._title_label.setObjectName("meetingDetailTitle")
        layout.addWidget(self._title_label, 1)

        self._retranscribe_btn = QPushButton("Retranscribe")
        self._retranscribe_btn.setObjectName("recordBtn")
        self._retranscribe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retranscribe_btn.setFixedWidth(100)
        self._retranscribe_btn.clicked.connect(self.retranscribe_requested.emit)
        layout.addWidget(self._retranscribe_btn)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("pauseBtn")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setFixedWidth(50)
        self._copy_btn.clicked.connect(self.copy_requested.emit)
        layout.addWidget(self._copy_btn)

        self._export_txt_btn = QPushButton("Export .txt")
        self._export_txt_btn.setObjectName("pauseBtn")
        self._export_txt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_txt_btn.setFixedWidth(80)
        self._export_txt_btn.clicked.connect(self.export_txt_requested.emit)
        layout.addWidget(self._export_txt_btn)

        self._export_md_btn = QPushButton("Export .md")
        self._export_md_btn.setObjectName("pauseBtn")
        self._export_md_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_md_btn.setFixedWidth(80)
        self._export_md_btn.clicked.connect(self.export_md_requested.emit)
        layout.addWidget(self._export_md_btn)

    def set_meeting(self, meeting: Meeting) -> None:
        date_str = meeting.created_at[:10] if meeting.created_at else ""
        self._title_label.setText(f"{meeting.name}  ({date_str})")
        # Only enable retranscribe if there's a WAV file
        self._retranscribe_btn.setEnabled(bool(meeting.wav_path))
