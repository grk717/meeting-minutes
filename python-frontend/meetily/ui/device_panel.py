"""Device selector panel for choosing audio input devices."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from meetily.audio.manager import AudioDevice, AudioManager


class DevicePanel(QWidget):
    """Panel with dropdowns for selecting mic and system audio devices.

    System audio has an "Auto-detect" option that picks the best loopback
    device automatically, so users don't have to guess.
    """

    mic_changed = Signal(object)  # AudioDevice or None
    system_changed = Signal(object)  # AudioDevice or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mic_devices: list[AudioDevice] = []
        self._sys_devices: list[AudioDevice] = []
        self._auto_detected_device: AudioDevice | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── Microphone selector ──
        mic_row = QHBoxLayout()
        mic_label = QLabel("Microphone")
        mic_label.setObjectName("deviceLabel")
        mic_label.setFixedWidth(120)
        self._mic_combo = QComboBox()
        self._mic_combo.setMinimumWidth(200)
        self._mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        mic_row.addWidget(mic_label)
        mic_row.addWidget(self._mic_combo, 1)
        layout.addLayout(mic_row)

        # ── System audio: toggle + auto/manual ──
        sys_header_row = QHBoxLayout()
        sys_label = QLabel("System Audio")
        sys_label.setObjectName("deviceLabel")
        sys_label.setFixedWidth(120)

        self._sys_toggle = QCheckBox("Capture system audio")
        self._sys_toggle.setChecked(False)
        self._sys_toggle.toggled.connect(self._on_sys_toggled)

        sys_header_row.addWidget(sys_label)
        sys_header_row.addWidget(self._sys_toggle, 1)
        layout.addLayout(sys_header_row)

        # Auto-detect status / manual override
        self._sys_detail_widget = QWidget()
        sys_detail_layout = QVBoxLayout(self._sys_detail_widget)
        sys_detail_layout.setContentsMargins(120, 0, 0, 0)
        sys_detail_layout.setSpacing(6)

        # Status label (shows auto-detected device or help)
        self._sys_status = QLabel("")
        self._sys_status.setObjectName("statusLabel")
        self._sys_status.setWordWrap(True)
        sys_detail_layout.addWidget(self._sys_status)

        # Manual override combo (hidden by default)
        manual_row = QHBoxLayout()
        self._sys_manual_check = QCheckBox("Manual:")
        self._sys_manual_check.setChecked(False)
        self._sys_manual_check.toggled.connect(self._on_manual_toggled)
        self._sys_combo = QComboBox()
        self._sys_combo.setMinimumWidth(200)
        self._sys_combo.setEnabled(False)
        self._sys_combo.currentIndexChanged.connect(self._on_sys_changed)
        manual_row.addWidget(self._sys_manual_check)
        manual_row.addWidget(self._sys_combo, 1)
        sys_detail_layout.addLayout(manual_row)

        self._sys_detail_widget.setVisible(False)
        layout.addWidget(self._sys_detail_widget)

        # ── Refresh button ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._refresh_btn = QPushButton("Refresh Devices")
        self._refresh_btn.setObjectName("refreshBtn")
        self._refresh_btn.clicked.connect(self.refresh_devices)
        btn_row.addWidget(self._refresh_btn)
        layout.addLayout(btn_row)

        self.refresh_devices()

    def refresh_devices(self) -> None:
        """Re-scan audio devices and repopulate dropdowns."""
        self._mic_combo.blockSignals(True)
        self._sys_combo.blockSignals(True)

        self._mic_combo.clear()
        self._sys_combo.clear()

        all_input = AudioManager.list_input_devices()

        # Separate real mics from loopback devices
        self._mic_devices = [d for d in all_input if not d.is_loopback]
        if not self._mic_devices:
            # Fallback: show all inputs if no non-loopback found
            self._mic_devices = all_input
        self._sys_devices = all_input

        # ── Mic dropdown ──
        self._mic_combo.addItem("None (no microphone)", None)
        default_input = AudioManager.default_input_device()
        default_mic_idx = 0

        for i, dev in enumerate(self._mic_devices):
            label = f"{dev.name}"
            if dev.is_loopback:
                label += "  [loopback]"
            self._mic_combo.addItem(label, dev.index)
            if dev.index == default_input:
                default_mic_idx = i + 1

        self._mic_combo.setCurrentIndex(default_mic_idx)

        # ── System audio dropdown (for manual override) ──
        self._sys_combo.addItem("(select device)", None)
        for dev in self._sys_devices:
            label = f"{dev.name}"
            if dev.is_loopback:
                label += "  [loopback]"
            label += f"  ({dev.hostapi_name})"
            self._sys_combo.addItem(label, dev.index)

        # ── Auto-detect ──
        self._auto_detected_device = AudioManager.auto_detect_system_device()
        self._update_sys_status()

        self._mic_combo.blockSignals(False)
        self._sys_combo.blockSignals(False)

    @property
    def selected_mic_device(self) -> int | None:
        return self._mic_combo.currentData()

    @property
    def selected_system_device(self) -> int | None:
        if not self._sys_toggle.isChecked():
            return None
        if self._sys_manual_check.isChecked():
            return self._sys_combo.currentData()
        if self._auto_detected_device is not None:
            return self._auto_detected_device.index
        return None

    # ── Signal handlers ──

    def _on_sys_toggled(self, checked: bool) -> None:
        self._sys_detail_widget.setVisible(checked)
        self._update_sys_status()

    def _on_manual_toggled(self, checked: bool) -> None:
        self._sys_combo.setEnabled(checked)
        self._update_sys_status()

    def _update_sys_status(self) -> None:
        if not self._sys_toggle.isChecked():
            return

        if self._sys_manual_check.isChecked():
            self._sys_status.setText("Using manually selected device")
            return

        if self._auto_detected_device:
            self._sys_status.setText(
                f"Auto-detected: {self._auto_detected_device.name} "
                f"({self._auto_detected_device.hostapi_name})"
            )
            self._sys_status.setStyleSheet("color: #4cd964;")
        else:
            help_text = AudioManager.get_system_audio_help()
            # Show just the first line in the label
            first_line = help_text.split("\n")[0]
            self._sys_status.setText(f"No device found. {first_line}")
            self._sys_status.setStyleSheet("color: #ff6b6b;")

    def _on_mic_changed(self, index: int) -> None:
        device_index = self._mic_combo.currentData()
        dev = None
        if device_index is not None:
            matching = [d for d in self._mic_devices if d.index == device_index]
            dev = matching[0] if matching else None
        self.mic_changed.emit(dev)

    def _on_sys_changed(self, index: int) -> None:
        device_index = self._sys_combo.currentData()
        dev = None
        if device_index is not None:
            matching = [d for d in self._sys_devices if d.index == device_index]
            dev = matching[0] if matching else None
        self.system_changed.emit(dev)
