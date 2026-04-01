"""Main application window with recording controls and UI.

Redesigned with a modern 2-column layout:
  - Left: Sidebar (meeting history)
  - Right: Stacked content area
    - Top: Recording controls OR meeting detail bar
    - Bottom: Transcript and summary panels side by side

The cramped 3-column layout is replaced with a spacious vertical flow
that gives each section room to breathe.
"""

from __future__ import annotations

import faulthandler
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, Slot, QObject
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QSplitter,
)

from meetily.audio.manager import AudioLevels, AudioManager, RecordingState
from meetily.storage.database import Meeting, MeetingDatabase
from meetily.summarization import SummarizationClient
from meetily.transcription import TranscriptionManager
from meetily.ui.device_panel import DevicePanel
from meetily.ui.level_bars import LevelBarsWidget
from meetily.ui.meeting_detail import MeetingDetailBar
from meetily.ui.retranscribe_widget import RetranscribeWidget
from meetily.ui.settings_dialog import SettingsDialog
from meetily.ui.sidebar import Sidebar
from meetily.ui.speaker_panel import SpeakerMappingPanel
from meetily.ui.summary_panel import SummaryPanel
from meetily.ui.toast import ToastManager
from meetily.ui.transcript_panel import TranscriptPanel
from meetily.ui.button_style import apply_button_style
from meetily.debug import DebugMonitor

log = logging.getLogger(__name__)

# Duration between autosaves (seconds) — protects against crash data loss
_AUTOSAVE_INTERVAL_MS = 60_000  # 1 minute


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
    _warning_signal = Signal(str)
    _transcript_signal = Signal(str, str)  # (text, timestamp)
    _summary_signal = Signal(str)  # summary text

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ZennoCall")
        self.setMinimumSize(700, 500)
        self.resize(1440, 800)

        # ── Crash protection ──
        self._setup_crash_handlers()

        # Debug monitor (singleton, starts only in debug mode)
        self._debug_monitor = DebugMonitor.instance()

        # Audio manager
        self._audio = AudioManager()
        self._audio.on_levels_updated = self._on_audio_levels
        self._audio.on_state_changed = self._on_audio_state
        self._audio.on_error = self._on_audio_error
        self._audio.on_warning = self._on_audio_warning

        # Transcription manager (created on recording start)
        self._transcription: TranscriptionManager | None = None

        # Track last saved WAV path for summarization
        self._last_saved_path: Path | None = None

        # Database
        self._db = MeetingDatabase()
        self._last_meeting_db_id: int | None = None
        self._current_detail_meeting: Meeting | None = None

        # Search debounce timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._refresh_sidebar)

        # Toast notifications
        self._toasts = ToastManager(self)

        # Connect internal signals (thread-safe bridge)
        self._levels_signal.connect(self._update_levels_ui)
        self._state_signal.connect(self._update_state_ui)
        self._error_signal.connect(self._show_error)
        self._warning_signal.connect(self._show_warning)
        self._transcript_signal.connect(self._on_transcript_received)
        self._summary_signal.connect(self._on_summary_received)

        # Duration timer
        self._duration_timer = QTimer(self)
        self._duration_timer.timeout.connect(self._update_duration)
        self._duration_timer.setInterval(500)

        # Autosave timer — periodically saves transcript to DB during recording
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave_recording)
        self._autosave_timer.setInterval(_AUTOSAVE_INTERVAL_MS)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        self._sidebar = Sidebar()
        self._sidebar.meeting_selected.connect(self._show_meeting_detail)
        self._sidebar.meeting_deleted.connect(self._on_meeting_deleted)
        self._sidebar.new_meeting_requested.connect(self._show_recording_view)
        self._sidebar.search_changed.connect(self._on_search_changed)

        # ── Main splitter: sidebar | content ──
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._sidebar)

        # ── Right pane (main content) ──
        right_pane = QWidget()
        right_pane.setStyleSheet("background-color: #0a1018;")
        right_pane.setMinimumWidth(400)
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # ── Header bar ──
        header_bar = QWidget()
        header_bar.setStyleSheet(
            "background-color: #0a1018;"
        )
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(20, 12, 20, 12)
        header_layout.setSpacing(8)

        app_title = QLabel("ZennoCall")
        app_title.setObjectName("appTitle")
        header_layout.addWidget(app_title)

        subtitle = QLabel("AI Meeting Assistant")
        subtitle.setObjectName("appSubtitle")
        header_layout.addWidget(subtitle)

        header_layout.addStretch()

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setObjectName("settingsBtn")
        apply_button_style(self._settings_btn, small=True)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self._open_settings)
        header_layout.addWidget(self._settings_btn)

        right_layout.addWidget(header_bar)

        # ── Meeting detail bar (hidden by default) ──
        self._detail_bar = MeetingDetailBar()
        self._detail_bar.setVisible(False)
        self._detail_bar.back_requested.connect(self._show_recording_view)
        self._detail_bar.retranscribe_requested.connect(self._on_retranscribe_requested)
        self._detail_bar.copy_requested.connect(self._on_copy_meeting)
        self._detail_bar.export_txt_requested.connect(self._on_export_txt)
        self._detail_bar.export_md_requested.connect(self._on_export_md)
        right_layout.addWidget(self._detail_bar)

        # ── Retranscribe progress widget (hidden by default) ──
        self._retranscribe_widget = RetranscribeWidget()
        self._retranscribe_widget.completed.connect(self._on_retranscribe_completed)
        self._retranscribe_widget.failed.connect(self._on_retranscribe_failed)
        self._retranscribe_widget.cancelled.connect(self._on_retranscribe_cancelled)
        right_layout.addWidget(self._retranscribe_widget)

        # ── Speaker name mapping panel (hidden by default) ──
        self._speaker_panel = SpeakerMappingPanel()
        self._speaker_panel.mapping_applied.connect(self._on_speaker_mapping_applied)
        right_layout.addWidget(self._speaker_panel)

        # ── Recording controls section ──
        self._rec_widget = QWidget()
        self._rec_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        rec_outer = QVBoxLayout(self._rec_widget)
        rec_outer.setContentsMargins(24, 20, 24, 8)
        rec_outer.setSpacing(16)

        # Recording card
        rec_card = QWidget()
        rec_card.setObjectName("recordingSection")
        rec_card.setStyleSheet(
            "#recordingSection { background-color: #0e1620; "
            "border: 1px solid #172230; border-radius: 12px; }"
        )
        rec_card_layout = QVBoxLayout(rec_card)
        rec_card_layout.setContentsMargins(16, 16, 16, 16)
        rec_card_layout.setSpacing(12)

        # Meeting name row
        name_row = QHBoxLayout()
        name_row.setSpacing(12)

        name_section = QVBoxLayout()
        name_section.setSpacing(4)
        name_label = QLabel("Meeting Name")
        name_label.setObjectName("deviceLabel")
        name_section.addWidget(name_label)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Team Standup, Sprint Review, 1-on-1...")
        self._name_input.setObjectName("meetingNameInput")
        name_section.addWidget(self._name_input)
        name_row.addLayout(name_section, 1)

        rec_card_layout.addLayout(name_row)

        # Device selection (compact)
        self._device_panel = DevicePanel()
        rec_card_layout.addWidget(self._device_panel)

        # Divider
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setObjectName("divider")
        rec_card_layout.addWidget(divider)

        # Recording visualization area
        viz_area = QWidget()
        viz_layout = QHBoxLayout(viz_area)
        viz_layout.setContentsMargins(0, 8, 0, 8)
        viz_layout.setSpacing(16)

        # Left: Mic level bars + label
        mic_col = QVBoxLayout()
        mic_col.setSpacing(6)
        self._mic_bars = LevelBarsWidget()
        self._mic_bars.setFixedSize(80, 64)
        mic_label = QLabel("MIC")
        mic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mic_label.setObjectName("levelLabel")
        mic_col.addWidget(self._mic_bars, 0, Qt.AlignmentFlag.AlignCenter)
        mic_col.addWidget(mic_label)

        # Center: Duration + status
        center_col = QVBoxLayout()
        center_col.setSpacing(4)
        center_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._duration_label = QLabel("00:00")
        self._duration_label.setObjectName("durationLabel")
        self._duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_col.addWidget(self._duration_label)

        self._status_label = QLabel("Ready to record")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_col.addWidget(self._status_label)

        # Right: System level bars + label
        sys_col = QVBoxLayout()
        sys_col.setSpacing(6)
        self._sys_bars = LevelBarsWidget()
        self._sys_bars.setFixedSize(80, 64)
        sys_label = QLabel("SYSTEM")
        sys_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sys_label.setObjectName("levelLabel")
        sys_col.addWidget(self._sys_bars, 0, Qt.AlignmentFlag.AlignCenter)
        sys_col.addWidget(sys_label)

        viz_layout.addStretch()
        viz_layout.addLayout(mic_col)
        viz_layout.addLayout(center_col)
        viz_layout.addLayout(sys_col)
        viz_layout.addStretch()

        rec_card_layout.addWidget(viz_area)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setObjectName("pauseBtn")
        apply_button_style(self._pause_btn)
        self._pause_btn.setMinimumHeight(42)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.setVisible(False)
        self._pause_btn.clicked.connect(self._toggle_pause)

        self._record_btn = QPushButton("Start Recording")
        self._record_btn.setObjectName("recordBtn")
        self._record_btn.setMinimumHeight(42)
        self._record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._record_btn.clicked.connect(self._toggle_recording)

        btn_row.addStretch()
        btn_row.addWidget(self._pause_btn)
        btn_row.addWidget(self._record_btn)
        btn_row.addStretch()

        rec_card_layout.addLayout(btn_row)

        # Saved label
        self._saved_label = QLabel("")
        self._saved_label.setObjectName("savedLabel")
        self._saved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._saved_label.setWordWrap(True)
        rec_card_layout.addWidget(self._saved_label)

        rec_outer.addWidget(rec_card)

        right_layout.addWidget(self._rec_widget)

        # ── Content area: Transcript + Summary with visible splitter ──
        content_wrapper = QWidget()
        content_wrapper_layout = QVBoxLayout(content_wrapper)
        content_wrapper_layout.setContentsMargins(16, 12, 16, 16)
        content_wrapper_layout.setSpacing(0)

        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.setObjectName("contentSplitter")
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.setHandleWidth(9)

        # Transcript panel
        self._transcript_panel = TranscriptPanel()
        self._transcript_panel.setMinimumWidth(150)
        self._transcript_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._content_splitter.addWidget(self._transcript_panel)

        # Summary panel
        self._summary_panel = SummaryPanel()
        self._summary_panel.setMinimumWidth(150)
        self._summary_panel.generate_requested.connect(self._on_generate_summary)
        self._summary_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._content_splitter.addWidget(self._summary_panel)

        # Set default 60/40 split
        self._content_splitter.setStretchFactor(0, 3)
        self._content_splitter.setStretchFactor(1, 2)

        content_wrapper_layout.addWidget(self._content_splitter)

        right_layout.addWidget(content_wrapper, 1)  # stretch=1: takes remaining space

        self._splitter.addWidget(right_pane)
        self._splitter.setStretchFactor(0, 0)  # sidebar: minimal stretch
        self._splitter.setStretchFactor(1, 1)  # content: stretches
        # Set initial sidebar width (260px sidebar, rest for content)
        self._splitter.setSizes([260, 1180])
        root.addWidget(self._splitter, 1)

        # Load meeting history
        self._refresh_sidebar()

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

    # ── Crash protection & autosave ────────────────────────────

    def _setup_crash_handlers(self) -> None:
        """Install handlers that help diagnose silent crashes."""
        # faulthandler prints a Python traceback on SIGSEGV/SIGABRT/SIGFPE
        crash_dir = Path.home() / "Documents" / "ZennoCall" / "crash_logs"
        crash_dir.mkdir(parents=True, exist_ok=True)
        crash_file = crash_dir / f"crash_{os.getpid()}.log"
        try:
            self._crash_fh = open(crash_file, "w")
            faulthandler.enable(file=self._crash_fh, all_threads=True)
            log.info("Crash handler writing to: %s", crash_file)
        except Exception as e:
            log.warning("Could not enable faulthandler: %s", e)
            faulthandler.enable()  # fallback to stderr

        # Catch unhandled exceptions
        self._original_excepthook = sys.excepthook
        sys.excepthook = self._excepthook

    def _excepthook(self, exc_type, exc_value, exc_tb) -> None:
        """Global exception handler — emergency-save before crashing."""
        log.critical(
            "Unhandled exception — attempting emergency save",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        try:
            self._emergency_save()
        except Exception as e:
            log.error("Emergency save failed: %s", e)

        # Dump debug report if monitor was active
        if self._debug_monitor.is_running:
            try:
                path = self._debug_monitor.dump_report()
                log.info("Debug report saved before crash: %s", path)
            except Exception:
                pass

        # Call original hook
        if self._original_excepthook:
            self._original_excepthook(exc_type, exc_value, exc_tb)

    def _emergency_save(self) -> None:
        """Best-effort save of current transcript and audio on crash."""
        if self._audio.state == RecordingState.IDLE:
            return

        log.warning("Emergency save: attempting to persist recording data")

        transcript = self._transcript_panel.get_full_transcript()
        segments = list(self._transcript_panel.get_raw_segments())

        if not transcript and not segments:
            log.warning("Emergency save: no transcript data to save")
            return

        try:
            meeting = Meeting(
                name=(self._name_input.text().strip() or "Untitled Meeting")
                     + " (recovered)",
                created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                duration_secs=self._audio.get_recording_duration(),
                wav_path="",
                transcript_text=transcript,
                transcript_segments=segments,
            )
            mid = self._db.save_meeting(meeting)
            log.warning("Emergency save: transcript saved as meeting id=%d", mid)
        except Exception as e:
            # Last resort: write to a file
            log.error("Emergency DB save failed: %s — writing to file", e)
            try:
                emergency_path = (
                    Path.home() / "Documents" / "ZennoCall"
                    / f"emergency_{int(time.time())}.txt"
                )
                emergency_path.write_text(transcript, encoding="utf-8")
                log.warning("Emergency file save: %s", emergency_path)
            except Exception:
                pass

    def _autosave_recording(self) -> None:
        """Periodically save transcript to DB during recording (crash protection)."""
        if self._audio.state != RecordingState.RECORDING:
            return

        transcript = self._transcript_panel.get_full_transcript()
        segments = list(self._transcript_panel.get_raw_segments())
        if not transcript:
            return

        try:
            meeting_name = (
                self._name_input.text().strip() or "Untitled Meeting"
            )
            if self._last_meeting_db_id:
                # Update existing autosave record
                self._db.update_transcript(
                    self._last_meeting_db_id, transcript, segments
                )
                log.debug("Autosaved transcript (%d segments)", len(segments))
            else:
                # Create initial autosave record
                meeting = Meeting(
                    name=meeting_name + " (recording...)",
                    created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    duration_secs=self._audio.get_recording_duration(),
                    transcript_text=transcript,
                    transcript_segments=segments,
                )
                self._last_meeting_db_id = self._db.save_meeting(meeting)
                log.info(
                    "Autosave: created meeting id=%d", self._last_meeting_db_id
                )
                self._refresh_sidebar()
        except Exception as e:
            log.error("Autosave failed: %s", e)

        # Update debug monitor transcript count
        if self._debug_monitor.is_running:
            self._debug_monitor.track_transcript_count(len(segments))

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

        # Start autosave timer
        self._autosave_timer.start()

        # Start debug monitor if in debug mode
        if os.environ.get("MEETILY_DEBUG"):
            self._debug_monitor.start()
            self._debug_monitor.snapshot("recording_start")

    def _stop_recording(self) -> None:
        # Stop autosave and debug monitor
        self._autosave_timer.stop()
        if self._debug_monitor.is_running:
            self._debug_monitor.snapshot("recording_stop")
            self._debug_monitor.dump_report()
            self._debug_monitor.stop()

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

        # Save to database — update autosave record if it exists, else create new
        autosave_id = self._last_meeting_db_id
        self._last_meeting_db_id = None
        if saved_path or transcript:
            try:
                segments = list(self._transcript_panel.get_raw_segments())
                meeting_name = self._name_input.text().strip() or "Untitled Meeting"
                if autosave_id:
                    # Update the autosave record with final data
                    self._db.update_transcript(autosave_id, transcript, segments)
                    # Update name (remove " (recording...)" suffix) and wav_path
                    conn = self._db._conn
                    now = time.strftime("%Y-%m-%dT%H:%M:%S")
                    conn.execute(
                        "UPDATE meetings SET name=?, wav_path=?, duration_secs=?, updated_at=? WHERE id=?",
                        (meeting_name, str(saved_path) if saved_path else "", self._audio.get_recording_duration(), now, autosave_id),
                    )
                    conn.commit()
                    self._last_meeting_db_id = autosave_id
                else:
                    meeting = Meeting(
                        name=meeting_name,
                        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                        duration_secs=self._audio.get_recording_duration(),
                        wav_path=str(saved_path) if saved_path else "",
                        transcript_text=transcript,
                        transcript_segments=segments,
                    )
                    self._last_meeting_db_id = self._db.save_meeting(meeting)
                self._refresh_sidebar()
            except Exception as e:
                log.error("Failed to save meeting to DB: %s", e)
                self._toasts.error("Failed to save meeting to database")

        if saved_path:
            self._saved_label.setText(f"Saved: {saved_path.name}")
            self._toasts.success(f"Recording saved: {saved_path.name}")
        else:
            self._saved_label.setText("Recording discarded (too short or empty)")
            self._toasts.warning("Recording too short or empty -- not saved")

        # Enable generate button whenever we have a transcript
        if transcript:
            self._summary_panel.set_generate_enabled(True)

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
        log.info("Generate summary requested")
        transcript = self._transcript_panel.get_full_transcript()
        if not transcript:
            log.warning("No transcript available for summarization")
            QMessageBox.information(
                self,
                "No Transcript",
                "There is no transcript to summarize. Record a meeting first.",
            )
            return

        cfg = SettingsDialog.get_settings()
        log.info("LLM config: url=%s, model=%s", cfg["llm_url"], cfg["llm_model"])
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

    def _on_audio_warning(self, message: str) -> None:
        self._warning_signal.emit(message)

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
        if summary.startswith("Summarization failed:"):
            self._summary_panel.set_summary(summary)
            self._toasts.error(summary)
            return

        self._summary_panel.set_summary(summary)
        self._toasts.success("Summary generated")

        # Determine which meeting to update
        db_id = None
        if self._current_detail_meeting and self._current_detail_meeting.id:
            db_id = self._current_detail_meeting.id
        elif self._last_meeting_db_id:
            db_id = self._last_meeting_db_id

        if db_id:
            try:
                self._db.update_summary(db_id, summary)
                self._refresh_sidebar()
                if self._current_detail_meeting and self._current_detail_meeting.id == db_id:
                    self._current_detail_meeting = self._db.get_meeting(db_id)
            except Exception as e:
                log.error("Failed to save summary to DB: %s", e)
                self._toasts.error("Failed to save summary to database")

    @Slot(str)
    def _show_error(self, message: str) -> None:
        self._toasts.error(message)

    @Slot(str)
    def _show_warning(self, message: str) -> None:
        self._toasts.warning(message)

    def _update_duration(self) -> None:
        secs = self._audio.get_recording_duration()
        mins = int(secs) // 60
        secs_remainder = int(secs) % 60
        self._duration_label.setText(f"{mins:02d}:{secs_remainder:02d}")

    # ── Sidebar / meeting browsing ──────────────────────────────

    def _refresh_sidebar(self) -> None:
        query = self._sidebar.search_query
        if query:
            meetings = self._db.search_meetings(query)
        else:
            meetings = self._db.list_meetings()
        self._sidebar.populate(meetings)

    def _on_search_changed(self, text: str) -> None:
        self._search_timer.start()  # debounce 300ms

    def _show_meeting_detail(self, meeting_id: int) -> None:
        if self._audio.state != RecordingState.IDLE:
            QMessageBox.information(
                self,
                "Recording Active",
                "Please stop the current recording before viewing past meetings.",
            )
            return

        meeting = self._db.get_meeting(meeting_id)
        if meeting is None:
            return

        self._current_detail_meeting = meeting
        self._sidebar.set_selected(meeting_id)

        # Switch to detail mode
        self._rec_widget.setVisible(False)
        self._detail_bar.setVisible(True)
        self._detail_bar.set_meeting(meeting)

        # Populate transcript panel (apply speaker names if available)
        self._transcript_panel.clear()
        has_speakers = any(
            len(seg) >= 3 and seg[2] for seg in meeting.transcript_segments
        )
        if has_speakers:
            display_segments = self._apply_speaker_names(
                meeting.transcript_segments, meeting.speaker_names
            )
            for ts, text in display_segments:
                self._transcript_panel.add_segment(text, ts)
            # Show speaker mapping panel
            speaker_ids = sorted({
                str(seg[2]) for seg in meeting.transcript_segments
                if len(seg) >= 3 and seg[2]
            })
            self._speaker_panel.set_speakers(speaker_ids, meeting.speaker_names)
        else:
            for timestamp, text in meeting.transcript_segments:
                self._transcript_panel.add_segment(text, timestamp)
            self._speaker_panel.reset()
        if not meeting.transcript_segments and meeting.transcript_text:
            self._transcript_panel.add_segment(meeting.transcript_text, "")

        # Populate summary panel
        self._summary_panel.clear()
        if meeting.summary_text:
            self._summary_panel.set_summary(meeting.summary_text)
        elif meeting.transcript_text or meeting.transcript_segments:
            self._summary_panel.set_generate_enabled(True)

    def _show_recording_view(self) -> None:
        self._current_detail_meeting = None
        self._rec_widget.setVisible(True)
        self._detail_bar.setVisible(False)
        self._retranscribe_widget.reset()
        self._speaker_panel.reset()
        self._sidebar.set_selected(None)

        if self._audio.state == RecordingState.IDLE:
            self._transcript_panel.clear()
            self._summary_panel.clear()

    def _on_meeting_deleted(self, meeting_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Meeting",
            "Are you sure you want to delete this meeting?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._db.delete_meeting(meeting_id)
        self._toasts.success("Meeting deleted")

        if (
            self._current_detail_meeting
            and self._current_detail_meeting.id == meeting_id
        ):
            self._show_recording_view()

        self._refresh_sidebar()

    # ── Copy / export ────────────────────────────────────────────

    def _on_copy_meeting(self) -> None:
        meeting = self._current_detail_meeting
        if not meeting:
            return
        text = f"Meeting: {meeting.name}\nDate: {meeting.created_at}\n\n"
        text += "TRANSCRIPT\n" + meeting.transcript_text + "\n"
        if meeting.summary_text:
            text += "\nSUMMARY\n" + meeting.summary_text
        QApplication.clipboard().setText(text)
        self._toasts.success("Copied to clipboard")

    def _on_export_txt(self) -> None:
        meeting = self._current_detail_meeting
        if not meeting:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Meeting", f"{meeting.name}.txt", "Text Files (*.txt)"
        )
        if path:
            content = f"Meeting: {meeting.name}\nDate: {meeting.created_at}\n\n"
            content += meeting.transcript_text
            if meeting.summary_text:
                content += f"\n\nSummary:\n{meeting.summary_text}"
            Path(path).write_text(content, encoding="utf-8")
            self._toasts.success(f"Exported to {Path(path).name}")

    def _on_export_md(self) -> None:
        meeting = self._current_detail_meeting
        if not meeting:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Meeting", f"{meeting.name}.md", "Markdown Files (*.md)"
        )
        if path:
            content = f"# {meeting.name}\n\n"
            content += f"**Date:** {meeting.created_at}\n\n"
            content += "## Transcript\n\n"
            display_segs = self._apply_speaker_names(
                meeting.transcript_segments, meeting.speaker_names
            )
            for ts, text in display_segs:
                content += f"- **[{ts}]** {text}\n"
            if meeting.summary_text:
                content += f"\n## Summary\n\n{meeting.summary_text}\n"
            Path(path).write_text(content, encoding="utf-8")
            self._toasts.success(f"Exported to {Path(path).name}")

    # ── Retranscription ───────────────────────────────────────────

    def _on_retranscribe_requested(self) -> None:
        meeting = self._current_detail_meeting
        if not meeting or not meeting.wav_path:
            QMessageBox.warning(
                self,
                "No Audio File",
                "This meeting has no audio file to retranscribe.",
            )
            return

        wav = Path(meeting.wav_path)
        if not wav.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"Audio file not found:\n{meeting.wav_path}",
            )
            return

        cfg = SettingsDialog.get_settings()
        if not cfg["backend_url"]:
            QMessageBox.warning(
                self,
                "Backend Not Configured",
                "Please configure the backend URL in Settings.",
            )
            return

        self._retranscribe_widget.start_job(
            wav_path=meeting.wav_path,
            meeting_name=meeting.name,
            asr_url=cfg["asr_url"],
            asr_api_key=cfg["asr_api_key"],
            backend_url=cfg["backend_url"],
        )

    def _on_retranscribe_completed(self, transcript: str, segments: list) -> None:
        meeting = self._current_detail_meeting
        if not meeting:
            self._retranscribe_widget.reset()
            return

        # Convert API segments to 3-tuples: (MM:SS, text, speaker_id)
        converted_segments = []
        speaker_ids = set()
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            text = (seg.get("Content") or seg.get("content")
                    or seg.get("text") or seg.get("Text") or "")
            text = str(text).strip()
            if not text or text == "[Silence]":
                continue
            start = seg.get("Start", seg.get("start", 0.0))
            try:
                start = float(start)
            except (TypeError, ValueError):
                start = 0.0
            speaker = seg.get("Speaker", seg.get("speaker", None))
            mins = int(start) // 60
            secs = int(start) % 60
            speaker_id = str(speaker) if speaker is not None else ""
            if speaker_id:
                speaker_ids.add(speaker_id)
            converted_segments.append((f"{mins:02d}:{secs:02d}", text, speaker_id))

        # Build display text with speaker labels
        display_segments = self._apply_speaker_names(converted_segments, {})
        full_text = "\n".join(
            f"[{ts}]  {text}" for ts, text in display_segments
        )
        if not full_text:
            full_text = transcript

        # Update DB
        try:
            self._db.update_transcript(meeting.id, full_text, converted_segments)
            self._current_detail_meeting = self._db.get_meeting(meeting.id)
        except Exception as e:
            log.error("Failed to save retranscription to DB: %s", e)
            self._toasts.error("Failed to save retranscription to database")

        self._toasts.success("Retranscription complete")

        # Refresh transcript panel
        self._render_transcript(display_segments, transcript)

        # Show speaker mapping panel if speakers were detected
        if speaker_ids:
            saved_names = meeting.speaker_names or {}
            self._speaker_panel.set_speakers(sorted(speaker_ids), saved_names)
        else:
            self._speaker_panel.reset()

        # Enable summary generation with new transcript
        self._summary_panel.set_generate_enabled(True)
        self._refresh_sidebar()
        self._retranscribe_widget.reset()

    @staticmethod
    def _apply_speaker_names(
        segments: list[tuple], names: dict[str, str]
    ) -> list[tuple[str, str]]:
        """Convert 3-tuples (ts, text, speaker_id) to 2-tuples (ts, display_text).

        Applies speaker name mapping: if a name is set for a speaker ID,
        use it; otherwise fall back to "Speaker N:".
        Also handles legacy 2-tuples gracefully.
        """
        result = []
        for seg in segments:
            if len(seg) >= 3:
                ts, text, speaker_id = seg[0], seg[1], seg[2]
            else:
                ts, text = seg[0], seg[1]
                speaker_id = ""

            if speaker_id:
                label = names.get(str(speaker_id), f"Speaker {speaker_id}")
                display = f"{label}: {text}"
            else:
                display = text
            result.append((ts, display))
        return result

    def _render_transcript(
        self, display_segments: list[tuple[str, str]], fallback: str = ""
    ) -> None:
        """Clear and re-populate the transcript panel."""
        self._transcript_panel.clear()
        for ts, text in display_segments:
            self._transcript_panel.add_segment(text, ts)
        if not display_segments and fallback:
            self._transcript_panel.add_segment(fallback, "")

    def _on_speaker_mapping_applied(self, mapping: dict) -> None:
        """User clicked Apply on the speaker mapping panel."""
        meeting = self._current_detail_meeting
        if not meeting:
            return

        # Save mapping to DB
        try:
            self._db.update_speaker_names(meeting.id, mapping)
            self._current_detail_meeting = self._db.get_meeting(meeting.id)
            meeting = self._current_detail_meeting
        except Exception as e:
            log.error("Failed to save speaker names: %s", e)
            self._toasts.error("Failed to save speaker names")
            return

        # Re-render transcript with new names
        display_segments = self._apply_speaker_names(
            meeting.transcript_segments, mapping
        )
        self._render_transcript(display_segments, meeting.transcript_text)

        # Rebuild full transcript text with names applied and save to DB
        full_text = "\n".join(
            f"[{ts}]  {text}" for ts, text in display_segments
        )
        if full_text:
            try:
                self._db.update_transcript(
                    meeting.id, full_text, meeting.transcript_segments
                )
                self._current_detail_meeting = self._db.get_meeting(meeting.id)
            except Exception as e:
                log.error("Failed to update transcript text: %s", e)

        self._toasts.success("Speaker names updated")

    def _on_retranscribe_failed(self, error: str) -> None:
        self._toasts.error(f"Retranscription failed: {error}")
        self._retranscribe_widget.reset()

    def _on_retranscribe_cancelled(self) -> None:
        self._retranscribe_widget.reset()

    # ── Window events ──────────────────────────────────────────

    # Aspect ratio limits: prevent unusably narrow or short windows
    _MIN_ASPECT = 4 / 3   # width/height — can't be too narrow/tall
    _MAX_ASPECT = 21 / 9  # width/height — can't be too wide/short

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Enforce aspect ratio bounds
        w, h = self.width(), self.height()
        aspect = w / max(h, 1)
        if aspect < self._MIN_ASPECT:
            # Too narrow — increase width to match min aspect
            new_w = int(h * self._MIN_ASPECT)
            self.resize(new_w, h)
            return
        if aspect > self._MAX_ASPECT:
            # Too wide — increase height to match max aspect
            new_h = int(w / self._MAX_ASPECT)
            self.resize(w, new_h)
            return
        # Reposition toasts to adapt to new window size
        self._toasts._reposition()

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

        # Stop debug monitor
        if self._debug_monitor.is_running:
            self._debug_monitor.dump_report()
            self._debug_monitor.stop()

        self._autosave_timer.stop()
        self._mic_bars.stop()
        self._sys_bars.stop()
        self._duration_timer.stop()
        self._db.close()

        # Close crash log file handle
        if hasattr(self, "_crash_fh"):
            try:
                self._crash_fh.close()
            except Exception:
                pass

        event.accept()
