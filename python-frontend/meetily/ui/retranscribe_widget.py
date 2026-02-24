"""Inline widget showing retranscription job progress.

Redesigned with cleaner status display and cancel action.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from meetily.transcription.retranscribe_client import RetranscribeClient

log = logging.getLogger(__name__)


class RetranscribeWidget(QWidget):
    """Shows retranscription progress: queued -> processing -> done/failed."""

    # (full_transcript, segments as list of dicts)
    completed = Signal(str, list)
    failed = Signal(str)
    cancelled = Signal()

    # Internal signals for thread-safe UI updates
    _submit_done = Signal(dict)
    _submit_error = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("retranscribeWidget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Status indicator dot
        self._dot = QLabel("\u2022")
        self._dot.setStyleSheet("color: #6366f1; font-size: 18px;")
        self._dot.setFixedWidth(14)
        layout.addWidget(self._dot)

        self._status_label = QLabel("")
        self._status_label.setObjectName("retranscribeStatus")
        layout.addWidget(self._status_label, 1)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("detailActionBtn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel_btn)

        self._client: RetranscribeClient | None = None
        self._job_id: str | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._poll)

        self._submit_done.connect(self._on_submit_done)
        self._submit_error.connect(self._on_submit_error)

        self.setVisible(False)

    def start_job(
        self,
        wav_path: str,
        meeting_name: str,
        asr_url: str,
        asr_api_key: str = "",
        asr_model: str = "whisper-1",
        backend_url: str = "http://localhost:5167",
    ) -> None:
        """Submit a retranscription job and start polling."""
        self._client = RetranscribeClient(backend_url)
        self._job_id = None
        self._status_label.setText("Uploading audio...")
        self._dot.setStyleSheet("color: #fbbf24; font-size: 18px;")
        self._cancel_btn.setEnabled(True)
        self.setVisible(True)

        def _submit() -> None:
            try:
                result = self._client.submit(
                    wav_path=wav_path,
                    meeting_name=meeting_name,
                    asr_url=asr_url,
                    asr_api_key=asr_api_key,
                    asr_model=asr_model,
                )
                self._submit_done.emit(result)
            except Exception as e:
                self._submit_error.emit(str(e))

        thread = threading.Thread(target=_submit, daemon=True)
        thread.start()

    def cancel_job(self) -> None:
        """Cancel the current job."""
        self._on_cancel()

    def _on_submit_done(self, result: dict) -> None:
        self._job_id = result.get("job_id")
        pos = result.get("queue_position", 0)
        if pos > 0:
            self._status_label.setText(f"Queued (position {pos})...")
        else:
            self._status_label.setText("Queued...")
        self._dot.setStyleSheet("color: #6366f1; font-size: 18px;")
        self._poll_timer.start()

    def _on_submit_error(self, error: str) -> None:
        log.error("Retranscription submit failed: %s", error)
        self._status_label.setText("Upload failed")
        self._dot.setStyleSheet("color: #f87171; font-size: 18px;")
        self._cancel_btn.setEnabled(False)
        self.failed.emit(f"Failed to submit: {error}")

    def _poll(self) -> None:
        if not self._client or not self._job_id:
            return

        try:
            result = self._client.poll_status(self._job_id)
        except Exception as e:
            log.error("Poll failed: %s", e)
            self._status_label.setText("Connection error, retrying...")
            return

        status = result.get("status", "")

        if status == "queued":
            pos = result.get("queue_position", 0)
            if pos > 0:
                self._status_label.setText(f"Queued (position {pos})...")
            else:
                self._status_label.setText("Queued...")
            self._dot.setStyleSheet("color: #6366f1; font-size: 18px;")

        elif status == "processing":
            progress = result.get("progress", 0.0)
            pct = int(progress * 100)
            self._status_label.setText(f"Transcribing... {pct}%")
            self._dot.setStyleSheet("color: #fbbf24; font-size: 18px;")

        elif status == "completed":
            self._poll_timer.stop()
            self._status_label.setText("Complete")
            self._dot.setStyleSheet("color: #34d399; font-size: 18px;")
            self._cancel_btn.setEnabled(False)
            transcript = result.get("transcript", "")
            segments = result.get("segments", [])
            self.completed.emit(transcript, segments)

        elif status == "failed":
            self._poll_timer.stop()
            error = result.get("error", "Unknown error")
            self._status_label.setText(f"Failed: {error}")
            self._dot.setStyleSheet("color: #f87171; font-size: 18px;")
            self._cancel_btn.setEnabled(False)
            self.failed.emit(error)

        elif status == "cancelled":
            self._poll_timer.stop()
            self._status_label.setText("Cancelled")
            self._dot.setStyleSheet("color: #6b6b80; font-size: 18px;")
            self._cancel_btn.setEnabled(False)
            self.cancelled.emit()

    def _on_cancel(self) -> None:
        self._poll_timer.stop()
        self._cancel_btn.setEnabled(False)

        if self._client and self._job_id:
            try:
                self._client.cancel(self._job_id)
            except Exception as e:
                log.warning("Cancel request failed: %s", e)

        self._status_label.setText("Cancelled")
        self._dot.setStyleSheet("color: #6b6b80; font-size: 18px;")
        self.cancelled.emit()

    def reset(self) -> None:
        """Hide widget and reset state."""
        self._poll_timer.stop()
        self._job_id = None
        self._client = None
        self.setVisible(False)
