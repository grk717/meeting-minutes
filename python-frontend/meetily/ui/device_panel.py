"""Compact device selector panel for choosing audio input devices.

Redesigned with cleaner layout and better visual hierarchy.
"""

from __future__ import annotations

import platform

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
from meetily.audio import loopback_win
from meetily.ui.button_style import apply_button_style


class DevicePanel(QWidget):
    """Panel with dropdowns for selecting mic and system audio devices.

    On Windows, system audio uses WASAPI loopback (PyAudioWPatch) to capture
    directly from speakers -- no virtual audio driver needed. The dropdown
    shows output devices (speakers/headphones) instead of input devices.

    On macOS/Linux, falls back to virtual input devices (BlackHole, monitors).
    """

    mic_changed = Signal(object)
    system_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mic_devices: list[AudioDevice] = []
        self._auto_detected_device = None
        self._auto_use_loopback = False
        self._manual_devices: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # ── Microphone selector ──
        mic_section = QVBoxLayout()
        mic_section.setSpacing(4)

        mic_label = QLabel("Microphone")
        mic_label.setObjectName("deviceLabel")
        mic_section.addWidget(mic_label)

        self._mic_combo = QComboBox()
        self._mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        mic_section.addWidget(self._mic_combo)

        layout.addLayout(mic_section)

        # ── System audio toggle ──
        sys_section = QVBoxLayout()
        sys_section.setSpacing(4)

        self._sys_toggle = QCheckBox("Capture system audio")
        self._sys_toggle.setChecked(False)
        self._sys_toggle.toggled.connect(self._on_sys_toggled)
        sys_section.addWidget(self._sys_toggle)

        # Detail area (shown when toggle is on)
        self._sys_detail_widget = QWidget()
        sys_detail_layout = QVBoxLayout(self._sys_detail_widget)
        sys_detail_layout.setContentsMargins(20, 4, 0, 0)
        sys_detail_layout.setSpacing(6)

        # Status label
        self._sys_status = QLabel("")
        self._sys_status.setObjectName("statusLabel")
        self._sys_status.setWordWrap(True)
        sys_detail_layout.addWidget(self._sys_status)

        # Manual override
        manual_row = QHBoxLayout()
        manual_row.setSpacing(8)
        self._sys_manual_check = QCheckBox("Manual:")
        self._sys_manual_check.setChecked(False)
        self._sys_manual_check.toggled.connect(self._on_manual_toggled)
        self._sys_combo = QComboBox()
        self._sys_combo.setEnabled(False)
        manual_row.addWidget(self._sys_manual_check)
        manual_row.addWidget(self._sys_combo, 1)
        sys_detail_layout.addLayout(manual_row)

        self._sys_detail_widget.setVisible(False)
        sys_section.addWidget(self._sys_detail_widget)

        layout.addLayout(sys_section)

        # ── Refresh button ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("refreshBtn")
        apply_button_style(self._refresh_btn, small=True)
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
            self._mic_devices = all_input

        # ── Mic dropdown ──
        self._mic_combo.addItem("None (no microphone)", None)
        default_input = AudioManager.default_input_device()
        default_mic_idx = 0

        for i, dev in enumerate(self._mic_devices):
            label = dev.name
            if dev.is_loopback:
                label += "  [loopback]"
            self._mic_combo.addItem(label, dev.index)
            if dev.index == default_input:
                default_mic_idx = i + 1

        self._mic_combo.setCurrentIndex(default_mic_idx)

        # ── System audio dropdown (manual override) ──
        self._sys_combo.addItem("(select device)", None)
        self._manual_devices = []

        if platform.system() == "Windows" and loopback_win.is_available():
            outputs = loopback_win.list_output_devices()
            for dev in outputs:
                label = dev.name
                if dev.is_default:
                    label += "  [Default]"
                self._sys_combo.addItem(label, dev.index)
                self._manual_devices.append(dev)
        else:
            for dev in all_input:
                label = dev.name
                if dev.is_loopback:
                    label += "  [loopback]"
                label += f"  ({dev.hostapi_name})"
                self._sys_combo.addItem(label, dev.index)
                self._manual_devices.append(dev)

        # ── Auto-detect ──
        self._auto_detected_device, self._auto_use_loopback = (
            AudioManager.auto_detect_system_device()
        )
        self._update_sys_status()

        self._mic_combo.blockSignals(False)
        self._sys_combo.blockSignals(False)

    @property
    def selected_mic_device(self) -> int | None:
        return self._mic_combo.currentData()

    @property
    def selected_system_device(self) -> int | None:
        """Get selected system audio device index, or None if disabled."""
        if not self._sys_toggle.isChecked():
            return None
        if self._sys_manual_check.isChecked():
            return self._sys_combo.currentData()
        if self._auto_detected_device is not None:
            return self._auto_detected_device.index
        return None

    @property
    def use_loopback(self) -> bool:
        """Whether to use WASAPI loopback mode for system audio."""
        if not self._sys_toggle.isChecked():
            return False
        if self._sys_manual_check.isChecked():
            return platform.system() == "Windows" and loopback_win.is_available()
        return self._auto_use_loopback

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
            if platform.system() == "Windows" and loopback_win.is_available():
                self._sys_status.setText("Select speakers/headphones to capture from")
            else:
                self._sys_status.setText("Select a virtual audio input device")
            self._sys_status.setStyleSheet("color: #5a7080;")
            return

        if self._auto_detected_device:
            name = self._auto_detected_device.name
            if self._auto_use_loopback:
                self._sys_status.setText(f"Auto: {name}")
            else:
                self._sys_status.setText(f"Auto: {name}")
            self._sys_status.setStyleSheet("color: #34b89a;")
        else:
            help_text = AudioManager.get_system_audio_help()
            first_line = help_text.split("\n")[0]
            self._sys_status.setText(f"Not available. {first_line}")
            self._sys_status.setStyleSheet("color: #d46464;")

    def _on_mic_changed(self, index: int) -> None:
        device_index = self._mic_combo.currentData()
        dev = None
        if device_index is not None:
            matching = [d for d in self._mic_devices if d.index == device_index]
            dev = matching[0] if matching else None
        self.mic_changed.emit(dev)

    def _on_sys_changed(self, index: int) -> None:
        pass  # Manual selection handled via properties
