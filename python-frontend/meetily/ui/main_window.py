"""Main application window with recording controls and UI."""

from __future__ import annotations

import logging
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
)

from meetily.audio.manager import AudioLevels, AudioManager, RecordingState
from meetily.ui.device_panel import DevicePanel
from meetily.ui.level_bars import LevelBarsWidget

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

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Meetily")
        self.setMinimumSize(520, 580)
        self.resize(560, 640)

        # Audio manager
        self._audio = AudioManager()
        self._audio.on_levels_updated = self._on_audio_levels
        self._audio.on_state_changed = self._on_audio_state
        self._audio.on_error = self._on_audio_error

        # Connect internal signals (thread-safe bridge)
        self._levels_signal.connect(self._update_levels_ui)
        self._state_signal.connect(self._update_state_ui)
        self._error_signal.connect(self._show_error)

        # Duration timer
        self._duration_timer = QTimer(self)
        self._duration_timer.timeout.connect(self._update_duration)
        self._duration_timer.setInterval(500)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        # ── Header ──
        header = QLabel("Meetily")
        header.setObjectName("appTitle")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(header)

        subtitle = QLabel("AI Meeting Assistant")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        root.addSpacing(4)

        # ── Meeting name ──
        name_group = QGroupBox("Meeting")
        name_layout = QHBoxLayout(name_group)
        name_label = QLabel("Name")
        name_label.setFixedWidth(50)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Team Standup, 1-on-1, Sprint Review...")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self._name_input, 1)
        root.addWidget(name_group)

        # ── Device selection ──
        device_group = QGroupBox("Audio Devices")
        device_layout = QVBoxLayout(device_group)
        self._device_panel = DevicePanel()
        device_layout.addWidget(self._device_panel)
        root.addWidget(device_group)

        # ── Recording section ──
        rec_group = QGroupBox("Recording")
        rec_layout = QVBoxLayout(rec_group)
        rec_layout.setSpacing(16)

        # Level bars
        bars_container = QWidget()
        bars_layout = QHBoxLayout(bars_container)
        bars_layout.setContentsMargins(0, 0, 0, 0)

        # Mic levels
        mic_col = QVBoxLayout()
        self._mic_bars = LevelBarsWidget()
        self._mic_bars.setFixedSize(60, 80)
        mic_label = QLabel("Mic")
        mic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mic_label.setObjectName("levelLabel")
        mic_col.addWidget(self._mic_bars, 0, Qt.AlignmentFlag.AlignCenter)
        mic_col.addWidget(mic_label)

        # System levels
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
        bars_layout.addSpacing(32)
        bars_layout.addLayout(sys_col)
        bars_layout.addStretch()

        rec_layout.addWidget(bars_container)

        # Duration label
        self._duration_label = QLabel("00:00")
        self._duration_label.setObjectName("durationLabel")
        self._duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_layout.addWidget(self._duration_label)

        # Status label
        self._status_label = QLabel("Ready to record")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_layout.addWidget(self._status_label)

        # Buttons row
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
        root.addWidget(rec_group)

        # ── Last saved info ──
        self._saved_label = QLabel("")
        self._saved_label.setObjectName("savedLabel")
        self._saved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._saved_label.setWordWrap(True)
        root.addWidget(self._saved_label)

        root.addStretch()

        # Start idle animation
        self._mic_bars.set_active(False)
        self._sys_bars.set_active(False)
        self._mic_bars._idle_timer.start()
        self._sys_bars._idle_timer.start()

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

        meeting_name = self._name_input.text().strip()
        self._audio.start_recording(
            mic_device=mic,
            system_device=sys_dev,
            use_loopback=self._device_panel.use_loopback,
            meeting_name=meeting_name,
        )

    def _stop_recording(self) -> None:
        saved_path = self._audio.stop_recording()
        if saved_path:
            self._saved_label.setText(f"Saved: {saved_path.name}")
        else:
            self._saved_label.setText("Recording discarded (too short or empty)")

    def _toggle_pause(self) -> None:
        if self._audio.state == RecordingState.RECORDING:
            self._audio.pause_recording()
        elif self._audio.state == RecordingState.PAUSED:
            self._audio.resume_recording()

    # ── Audio callbacks (called from audio thread) ──────────────

    def _on_audio_levels(self, levels: AudioLevels) -> None:
        # Bridge to main thread via signal
        self._levels_signal.emit(levels)

    def _on_audio_state(self, state: RecordingState) -> None:
        self._state_signal.emit(state)

    def _on_audio_error(self, message: str) -> None:
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

        self._mic_bars.stop()
        self._sys_bars.stop()
        self._duration_timer.stop()
        event.accept()
