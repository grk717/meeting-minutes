"""Device selector panel for choosing audio input devices."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from meetily.audio.manager import AudioDevice, AudioManager


class DevicePanel(QWidget):
    """Panel with dropdowns for selecting mic and system audio devices."""

    mic_changed = Signal(object)  # AudioDevice or None
    system_changed = Signal(object)  # AudioDevice or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mic_devices: list[AudioDevice] = []
        self._sys_devices: list[AudioDevice] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Microphone selector
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

        # System audio selector
        sys_row = QHBoxLayout()
        sys_label = QLabel("System Audio")
        sys_label.setObjectName("deviceLabel")
        sys_label.setFixedWidth(120)
        self._sys_combo = QComboBox()
        self._sys_combo.setMinimumWidth(200)
        self._sys_combo.currentIndexChanged.connect(self._on_sys_changed)
        sys_row.addWidget(sys_label)
        sys_row.addWidget(self._sys_combo, 1)
        layout.addLayout(sys_row)

        # Refresh button
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
        # Block signals during repopulation
        self._mic_combo.blockSignals(True)
        self._sys_combo.blockSignals(True)

        self._mic_combo.clear()
        self._sys_combo.clear()

        self._mic_devices = AudioManager.list_input_devices()
        self._sys_devices = AudioManager.list_input_devices()  # All inputs; loopback ones are marked

        # Mic dropdown
        self._mic_combo.addItem("None (no microphone)", None)
        default_input = AudioManager.default_input_device()
        default_mic_idx = 0

        for i, dev in enumerate(self._mic_devices):
            label = dev.name
            if dev.is_loopback:
                label += " (loopback)"
            self._mic_combo.addItem(label, dev.index)
            if dev.index == default_input:
                default_mic_idx = i + 1  # +1 for "None" entry

        # System audio dropdown
        self._sys_combo.addItem("None (no system audio)", None)
        for dev in self._sys_devices:
            label = dev.name
            if dev.is_loopback:
                label += " (loopback)"
            self._sys_combo.addItem(label, dev.index)

        self._mic_combo.setCurrentIndex(default_mic_idx)
        self._mic_combo.blockSignals(False)
        self._sys_combo.blockSignals(False)

    @property
    def selected_mic_device(self) -> int | None:
        return self._mic_combo.currentData()

    @property
    def selected_system_device(self) -> int | None:
        return self._sys_combo.currentData()

    def _on_mic_changed(self, index: int) -> None:
        device_index = self._mic_combo.currentData()
        if device_index is not None and 0 <= device_index < len(self._mic_devices):
            self.mic_changed.emit(self._mic_devices[device_index])
        else:
            self.mic_changed.emit(None)

    def _on_sys_changed(self, index: int) -> None:
        device_index = self._sys_combo.currentData()
        if device_index is not None:
            matching = [d for d in self._sys_devices if d.index == device_index]
            self.system_changed.emit(matching[0] if matching else None)
        else:
            self.system_changed.emit(None)
