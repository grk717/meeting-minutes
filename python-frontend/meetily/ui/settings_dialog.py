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
    "llm_url": "http://localhost:11434",
    "llm_api_key": "",
    "llm_model": "gpt-4o-mini",
    "backend_url": "http://localhost:5167",
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

        # LLM section
        llm_header = QLabel("Summarization (OpenAI-compatible chat completions)")
        llm_header.setWordWrap(True)
        layout.addWidget(llm_header)

        llm_form = QFormLayout()
        llm_form.setSpacing(10)

        self._llm_url_input = QLineEdit(current["llm_url"])
        self._llm_url_input.setPlaceholderText("http://localhost:11434")
        llm_form.addRow("LLM Endpoint URL:", self._llm_url_input)

        self._llm_key_input = QLineEdit(current["llm_api_key"])
        self._llm_key_input.setPlaceholderText("Optional API key")
        self._llm_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        llm_form.addRow("LLM API Key:", self._llm_key_input)

        self._llm_model_input = QLineEdit(current["llm_model"])
        self._llm_model_input.setPlaceholderText("gpt-4o-mini")
        llm_form.addRow("Model:", self._llm_model_input)

        layout.addLayout(llm_form)

        # Backend section
        backend_header = QLabel("Backend (retranscription queue)")
        backend_header.setWordWrap(True)
        layout.addWidget(backend_header)

        backend_form = QFormLayout()
        backend_form.setSpacing(10)

        self._backend_url_input = QLineEdit(current["backend_url"])
        self._backend_url_input.setPlaceholderText("http://localhost:5167")
        backend_form.addRow("Backend URL:", self._backend_url_input)

        layout.addLayout(backend_form)

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
        settings.setValue("llm_url", self._llm_url_input.text().strip())
        settings.setValue("llm_api_key", self._llm_key_input.text().strip())
        settings.setValue("llm_model", self._llm_model_input.text().strip())
        settings.setValue("backend_url", self._backend_url_input.text().strip())
        self.accept()

    @staticmethod
    def get_settings() -> dict[str, str]:
        """Load saved settings with defaults."""
        settings = QSettings("Meetily", "Meetily")
        return {
            "asr_url": settings.value("asr_url", _DEFAULTS["asr_url"]),
            "asr_api_key": settings.value("asr_api_key", _DEFAULTS["asr_api_key"]),
            "llm_url": settings.value("llm_url", _DEFAULTS["llm_url"]),
            "llm_api_key": settings.value("llm_api_key", _DEFAULTS["llm_api_key"]),
            "llm_model": settings.value("llm_model", _DEFAULTS["llm_model"]),
            "backend_url": settings.value("backend_url", _DEFAULTS["backend_url"]),
        }
