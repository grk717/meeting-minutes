"""Modern settings dialog for ASR/LLM/Backend endpoint configuration.

Redesigned with grouped sections, better labels, and visual hierarchy.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
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


def _make_field(
    label_text: str, value: str, placeholder: str, is_password: bool = False
) -> tuple[QWidget, QLineEdit]:
    """Create a labeled input field with consistent styling."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    label = QLabel(label_text)
    label.setObjectName("settingsFieldLabel")
    layout.addWidget(label)

    line_edit = QLineEdit(value)
    line_edit.setPlaceholderText(placeholder)
    if is_password:
        line_edit.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(line_edit)

    return container, line_edit


def _make_divider() -> QWidget:
    """Create a subtle horizontal divider."""
    divider = QWidget()
    divider.setFixedHeight(1)
    divider.setObjectName("divider")
    return divider


class SettingsDialog(QDialog):
    """Dialog for configuring ASR, LLM, and backend endpoint settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        current = self.get_settings()

        # ── ASR Section ──
        asr_section = QLabel("Speech Recognition")
        asr_section.setObjectName("settingsSection")
        layout.addWidget(asr_section)

        asr_desc = QLabel(
            "OpenAI-compatible transcription endpoint for real-time speech recognition."
        )
        asr_desc.setObjectName("settingsDesc")
        asr_desc.setWordWrap(True)
        layout.addWidget(asr_desc)

        url_widget, self._url_input = _make_field(
            "Endpoint URL", current["asr_url"], "http://localhost:8178"
        )
        layout.addWidget(url_widget)

        key_widget, self._key_input = _make_field(
            "API Key", current["asr_api_key"], "Optional", is_password=True
        )
        layout.addWidget(key_widget)

        layout.addWidget(_make_divider())

        # ── LLM Section ──
        llm_section = QLabel("Summarization")
        llm_section.setObjectName("settingsSection")
        layout.addWidget(llm_section)

        llm_desc = QLabel(
            "OpenAI-compatible chat completions endpoint for meeting summaries."
        )
        llm_desc.setObjectName("settingsDesc")
        llm_desc.setWordWrap(True)
        layout.addWidget(llm_desc)

        llm_url_widget, self._llm_url_input = _make_field(
            "Endpoint URL", current["llm_url"], "http://localhost:11434"
        )
        layout.addWidget(llm_url_widget)

        llm_key_widget, self._llm_key_input = _make_field(
            "API Key", current["llm_api_key"], "Optional", is_password=True
        )
        layout.addWidget(llm_key_widget)

        llm_model_widget, self._llm_model_input = _make_field(
            "Model", current["llm_model"], "gpt-4o-mini"
        )
        layout.addWidget(llm_model_widget)

        layout.addWidget(_make_divider())

        # ── Backend Section ──
        backend_section = QLabel("Backend")
        backend_section.setObjectName("settingsSection")
        layout.addWidget(backend_section)

        backend_desc = QLabel(
            "Meetily backend server for retranscription queue and meeting storage."
        )
        backend_desc.setObjectName("settingsDesc")
        backend_desc.setWordWrap(True)
        layout.addWidget(backend_desc)

        backend_url_widget, self._backend_url_input = _make_field(
            "Backend URL", current["backend_url"], "http://localhost:5167"
        )
        layout.addWidget(backend_url_widget)

        # ── Buttons ──
        layout.addSpacing(8)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
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
            "backend_url": settings.value(
                "backend_url", _DEFAULTS["backend_url"]
            ),
        }
