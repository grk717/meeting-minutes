"""Main application window with recording controls and UI."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QObject
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QGroupBox,
    QSizePolicy,
    QFrame,
    QSplitter,
)

from meetily.audio.manager import AudioLevels, AudioManager, RecordingState
from meetily.summarization import SummarizationClient
from meetily.transcription import TranscriptionManager
from meetily.ui.device_panel import DevicePanel
from meetily.ui.level_bars import LevelBarsWidget
from meetily.ui.settings_dialog import SettingsDialog
from meetily.ui.summary_panel import SummaryPanel
from meetily.ui.transcript_panel import TranscriptPanel

log = logging.getLogger(__name__)


class AudioWorker(QObject):
    """Runs audio operations off the main thread."""

    recording_stopped = Signal(object)  # Path or None
    error = Signal(str)

    def __init__(self, audio_manager: AudioManager) -> None:
        super().__init__()
        self._audio = audio_manager

    @Slot(int, object, str)
    def start_recording(self, mic_device: int, system_device: object, meeting_name: str) -> None:
        try:
            self._audio.start_recording(
                mic_device=mic_device if mic_device >= 0 else None,
                system_device=system_device,
                meeting_name=meeting_name,
            )
        except Exception as e:
            self.error.emit(str(e))

    @Slot()
    def stop_recording(self) -> None:
        try:
            path = self._audio.stop_recording()
            self.recording_stopped.emit(path)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Primary application window."""

    # Internal signals for thread-safe UI updates from audio callbacks
    _levels_signal = Signal(AudioLevels)
    _state_signal = Signal(RecordingState)
    _error_signal = Signal(str)
    _transcript_signal = Signal(str, str)  # (text, timestamp)
    _summary_signal = Signal(str)  # summary text

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Meetily")
        self.setMinimumSize(900, 600)
        self.resize(1200, 700)

        # Audio manager
        self._audio = AudioManager()
        self._audio.on_levels_updated = self._on_audio_levels
        self._audio.on_state_changed = self._on_audio_state
        self._audio.on_error = self._on_audio_error

        # Transcription manager (created on recording start)
        self._transcription: TranscriptionManager | None = None

        # Track last saved WAV path for summarization
        self._last_saved_path: Path | None = None

        # Connect internal signals (thread-safe bridge)
        self._levels_signal.connect(self._update_levels_ui)
        self._state_signal.connect(self._update_state_ui)
        self._error_signal.connect(self._show_error)
        self._transcript_signal.connect(self._on_transcript_received)
        self._summary_signal.connect(self._on_summary_received)

        # Duration timer
        self._duration_timer = QTimer(self)
        self._duration_timer.timeout.connect(self._update_duration)
        self._duration_timer.setInterval(500)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Header row ──
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Meetily")
        header.setObjectName("appTitle")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setObjectName("pauseBtn")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setFixedWidth(70)
        self._settings_btn.clicked.connect(self._open_settings)

        header_row.addStretch()
        header_row.addWidget(header)
        header_row.addStretch()
        header_row.addWidget(self._settings_btn)

        root.addLayout(header_row)

        subtitle = QLabel("AI Meeting Assistant")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        # ── Three-column horizontal layout ──
        columns = QHBoxLayout()
        columns.setSpacing(12)

        # ── Column 1: Recording ──
        rec_column = QVBoxLayout()
        rec_column.setSpacing(12)

        # Meeting name
        name_group = QGroupBox("Meeting")
        name_layout = QHBoxLayout(name_group)
        name_label = QLabel("Name")
        name_label.setFixedWidth(50)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Team Standup, 1-on-1...")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self._name_input, 1)
        rec_column.addWidget(name_group)

        # Device selection
        device_group = QGroupBox("Audio Devices")
        device_layout = QVBoxLayout(device_group)
        self._device_panel = DevicePanel()
        device_layout.addWidget(self._device_panel)
        rec_column.addWidget(device_group)

        # Recording controls
        rec_group = QGroupBox("Recording")
        rec_layout = QVBoxLayout(rec_group)
        rec_layout.setSpacing(12)

        # Level bars
        bars_container = QWidget()
        bars_layout = QHBoxLayout(bars_container)
        bars_layout.setContentsMargins(0, 0, 0, 0)

        mic_col = QVBoxLayout()
        self._mic_bars = LevelBarsWidget()
        self._mic_bars.setFixedSize(60, 80)
        mic_label = QLabel("Mic")
        mic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mic_label.setObjectName("levelLabel")
        mic_col.addWidget(self._mic_bars, 0, Qt.AlignmentFlag.AlignCenter)
        mic_col.addWidget(mic_label)

        sys_col = QVBoxLayout()
        self._sys_bars = LevelBarsWidget()
        self._sys_bars.setFixedSize(60, 80)
        sys_label = QLabel("System")
        sys_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sys_label.setObjectName("levelLabel")
        sys_col.addWidget(self._sys_bars, 0, Qt.AlignmentFlag.AlignCenter)
        sys_col.addWidget(sys_label)

        bars_layout.addStretch()
        bars_layout.addLayout(mic_col)
        bars_layout.addSpacing(24)
        bars_layout.addLayout(sys_col)
        bars_layout.addStretch()

        rec_layout.addWidget(bars_container)

        # Duration
        self._duration_label = QLabel("00:00")
        self._duration_label.setObjectName("durationLabel")
        self._duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_layout.addWidget(self._duration_label)

        # Status
        self._status_label = QLabel("Ready to record")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._record_btn = QPushButton("Start Recording")
        self._record_btn.setObjectName("recordBtn")
        self._record_btn.setMinimumHeight(48)
        self._record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._record_btn.clicked.connect(self._toggle_recording)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setObjectName("pauseBtn")
        self._pause_btn.setMinimumHeight(48)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.setVisible(False)
        self._pause_btn.clicked.connect(self._toggle_pause)

        btn_row.addStretch()
        btn_row.addWidget(self._pause_btn)
        btn_row.addWidget(self._record_btn)
        btn_row.addStretch()

        rec_layout.addLayout(btn_row)

        # Saved label
        self._saved_label = QLabel("")
        self._saved_label.setObjectName("savedLabel")
        self._saved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._saved_label.setWordWrap(True)
        rec_layout.addWidget(self._saved_label)

        rec_column.addWidget(rec_group)
        rec_column.addStretch()

        # Wrap recording column in a widget for the splitter
        rec_widget = QWidget()
        rec_widget.setLayout(rec_column)

        # ── Column 2: Transcript ──
        self._transcript_panel = TranscriptPanel()

        # ── Column 3: Summary ──
        self._summary_panel = SummaryPanel()
        self._summary_panel.generate_requested.connect(self._on_generate_summary)

        # Add columns
        columns.addWidget(rec_widget, 1)
        columns.addWidget(self._transcript_panel, 1)
        columns.addWidget(self._summary_panel, 1)

        root.addLayout(columns, 1)

        # Start idle animation
        self._mic_bars.set_active(False)
        self._sys_bars.set_active(False)
        self._mic_bars._idle_timer.start()
        self._sys_bars._idle_timer.start()

    # ── Settings ──────────────────────────────────────────────

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() and self._transcription:
            cfg = SettingsDialog.get_settings()
            self._transcription.update_settings(cfg["asr_url"], cfg["asr_api_key"])

    # ── Recording control ───────────────────────────────────────

    def _toggle_recording(self) -> None:
        if self._audio.state == RecordingState.IDLE:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        mic = self._device_panel.selected_mic_device
        sys_dev = self._device_panel.selected_system_device

        if mic is None and sys_dev is None:
            QMessageBox.warning(
                self,
                "No Device Selected",
                "Please select at least a microphone or system audio device.",
            )
            return

        # Start transcription pipeline
        cfg = SettingsDialog.get_settings()
        self._transcription = TranscriptionManager(cfg["asr_url"], cfg["asr_api_key"])
        self._transcription.on_transcript = self._on_transcript_from_worker
        self._transcription.on_error = self._on_transcription_error
        self._audio.on_audio_chunk = self._transcription.feed_audio
        self._transcription.start()
        self._transcript_panel.clear()
        self._summary_panel.clear()
        self._last_saved_path = None

        meeting_name = self._name_input.text().strip()
        self._audio.start_recording(
            mic_device=mic,
            system_device=sys_dev,
            use_loopback=self._device_panel.use_loopback,
            meeting_name=meeting_name,
        )

    def _stop_recording(self) -> None:
        # Disconnect audio chunk callback before stopping
        self._audio.on_audio_chunk = None

        saved_path = self._audio.stop_recording()

        if self._transcription:
            self._transcription.stop()
            self._transcription = None

        # Save transcript log
        transcript = self._transcript_panel.get_full_transcript()
        if saved_path and transcript:
            self._save_transcript_log(saved_path, transcript)

        self._last_saved_path = saved_path

        if saved_path:
            self._saved_label.setText(f"Saved: {saved_path.name}")
            # Enable generate button if we have a transcript
            if transcript:
                self._summary_panel.set_generate_enabled(True)
        else:
            self._saved_label.setText("Recording discarded (too short or empty)")

    def _toggle_pause(self) -> None:
        if self._audio.state == RecordingState.RECORDING:
            self._audio.pause_recording()
        elif self._audio.state == RecordingState.PAUSED:
            self._audio.resume_recording()

    # ── Transcript saving ─────────────────────────────────────

    def _save_transcript_log(self, wav_path: Path, transcript: str) -> None:
        """Save transcript as .txt next to the WAV file."""
        txt_path = wav_path.with_suffix(".txt")
        meeting_name = self._name_input.text().strip() or "Untitled Meeting"
        date_str = time.strftime("%Y-%m-%d %H:%M:%S")

        segments = self._transcript_panel.get_raw_segments()
        lines = [f"Meeting: {meeting_name}", f"Date: {date_str}", ""]
        for ts, text in segments:
            lines.append(f"[{ts}]  {text}")

        txt_path.write_text("\n".join(lines), encoding="utf-8")
        log.info("Transcript saved: %s", txt_path)

    # ── Summarization ─────────────────────────────────────────

    def _on_generate_summary(self) -> None:
        """Called when user clicks Generate Summary button."""
        transcript = self._transcript_panel.get_full_transcript()
        if not transcript:
            return

        cfg = SettingsDialog.get_settings()
        if not cfg["llm_url"]:
            QMessageBox.warning(
                self,
                "LLM Not Configured",
                "Please configure an LLM endpoint URL in Settings.",
            )
            return

        self._summary_panel.set_loading()

        client = SummarizationClient(cfg["llm_url"], cfg["llm_api_key"], cfg["llm_model"])
        meeting_name = self._name_input.text().strip() or "Untitled Meeting"
        wav_path = self._last_saved_path

        def worker() -> None:
            try:
                summary = client.summarize(transcript)
                # Save summary file next to WAV if available
                if wav_path:
                    summary_path = wav_path.with_name(wav_path.stem + "_summary.txt")
                    date_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    content = f"Meeting: {meeting_name}\nDate: {date_str}\n\n{summary}"
                    summary_path.write_text(content, encoding="utf-8")
                    log.info("Summary saved: %s", summary_path)
                self._summary_signal.emit(summary)
            except Exception as e:
                log.error("Summarization failed: %s", e)
                self._summary_signal.emit(f"Summarization failed: {e}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # ── Audio callbacks (called from audio thread) ──────────────

    def _on_audio_levels(self, levels: AudioLevels) -> None:
        self._levels_signal.emit(levels)

    def _on_audio_state(self, state: RecordingState) -> None:
        self._state_signal.emit(state)

    def _on_audio_error(self, message: str) -> None:
        self._error_signal.emit(message)

    # ── Transcription callbacks (called from worker thread) ─────

    def _on_transcript_from_worker(self, text: str, timestamp: str) -> None:
        self._transcript_signal.emit(text, timestamp)

    def _on_transcription_error(self, message: str) -> None:
        self._error_signal.emit(message)

    # ── UI updates (main thread) ────────────────────────────────

    @Slot(AudioLevels)
    def _update_levels_ui(self, levels: AudioLevels) -> None:
        self._mic_bars.set_level(levels.mic_rms, levels.mic_peak)
        self._sys_bars.set_level(levels.system_rms, levels.system_peak)

    @Slot(RecordingState)
    def _update_state_ui(self, state: RecordingState) -> None:
        if state == RecordingState.RECORDING:
            self._record_btn.setText("Stop Recording")
            self._record_btn.setObjectName("stopBtn")
            self._pause_btn.setText("Pause")
            self._pause_btn.setVisible(True)
            self._status_label.setText("Recording...")
            self._name_input.setEnabled(False)
            self._device_panel.setEnabled(False)
            self._mic_bars.set_active(True)
            self._sys_bars.set_active(True)
            self._duration_timer.start()

        elif state == RecordingState.PAUSED:
            self._pause_btn.setText("Resume")
            self._status_label.setText("Paused")
            self._mic_bars.set_active(False)
            self._sys_bars.set_active(False)
            self._duration_timer.stop()

        elif state == RecordingState.STOPPING:
            self._record_btn.setEnabled(False)
            self._pause_btn.setVisible(False)
            self._status_label.setText("Saving...")

        elif state == RecordingState.IDLE:
            self._record_btn.setText("Start Recording")
            self._record_btn.setObjectName("recordBtn")
            self._record_btn.setEnabled(True)
            self._pause_btn.setVisible(False)
            self._status_label.setText("Ready to record")
            self._name_input.setEnabled(True)
            self._device_panel.setEnabled(True)
            self._mic_bars.set_active(False)
            self._sys_bars.set_active(False)
            self._duration_timer.stop()
            self._duration_label.setText("00:00")

        # Force stylesheet refresh after objectName change
        self._record_btn.style().unpolish(self._record_btn)
        self._record_btn.style().polish(self._record_btn)

    @Slot(str, str)
    def _on_transcript_received(self, text: str, timestamp: str) -> None:
        self._transcript_panel.add_segment(text, timestamp)

    @Slot(str)
    def _on_summary_received(self, summary: str) -> None:
        self._summary_panel.set_summary(summary)

    @Slot(str)
    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Audio Error", message)

    def _update_duration(self) -> None:
        secs = self._audio.get_recording_duration()
        mins = int(secs) // 60
        secs_remainder = int(secs) % 60
        self._duration_label.setText(f"{mins:02d}:{secs_remainder:02d}")

    # ── Cleanup ─────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._audio.state != RecordingState.IDLE:
            reply = QMessageBox.question(
                self,
                "Recording in progress",
                "A recording is in progress. Stop and save before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Yes:
                self._stop_recording()

        if self._transcription:
            self._transcription.stop()
            self._transcription = None

        self._mic_bars.stop()
        self._sys_bars.stop()
        self._duration_timer.stop()
        event.accept()
