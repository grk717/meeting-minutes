"""Settings dialog for ASR endpoint configuration."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

_DEFAULTS = {
    "asr_url": "http://localhost:8178",
    "asr_api_key": "",
}


class SettingsDialog(QDialog):
    """Dialog for configuring ASR endpoint settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Description
        desc = QLabel("Configure the speech recognition API endpoint (OpenAI-compatible).")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        current = self.get_settings()

        self._url_input = QLineEdit(current["asr_url"])
        self._url_input.setPlaceholderText("http://localhost:8178")
        form.addRow("ASR Endpoint URL:", self._url_input)

        self._key_input = QLineEdit(current["asr_api_key"])
        self._key_input.setPlaceholderText("Optional API key")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API Key:", self._key_input)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        settings = QSettings("Meetily", "Meetily")
        settings.setValue("asr_url", self._url_input.text().strip())
        settings.setValue("asr_api_key", self._key_input.text().strip())
        self.accept()

    @staticmethod
    def get_settings() -> dict[str, str]:
        """Load saved settings with defaults."""
        settings = QSettings("Meetily", "Meetily")
        return {
            "asr_url": settings.value("asr_url", _DEFAULTS["asr_url"]),
            "asr_api_key": settings.value("asr_api_key", _DEFAULTS["asr_api_key"]),
        }
