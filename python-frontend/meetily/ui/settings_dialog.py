"""Modern settings dialog for ASR/LLM/Backend endpoint configuration.

Organized into tabs: Transcription, Retranscription, Summarization.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

_DEFAULTS = {
    "api_key": "",
    "asr_url": "http://localhost:8178",
    "llm_url": "http://localhost:11434",
    "llm_system_prompt": "",
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


class SettingsDialog(QDialog):
    """Dialog for configuring ASR, LLM, and backend endpoint settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        current = self.get_settings()

        # ── Tab widget ──
        tabs = QTabWidget()
        tabs.addTab(self._build_authorization_tab(current), "Authorization")
        tabs.addTab(self._build_transcription_tab(current), "Transcription")
        tabs.addTab(self._build_retranscription_tab(current), "Retranscription")
        tabs.addTab(self._build_summarization_tab(current), "Summarization")
        layout.addWidget(tabs)

        # ── Buttons ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_authorization_tab(self, current: dict[str, str]) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 20, 16, 16)

        desc = QLabel(
            "API key sent as X-API-Key header with every request to "
            "transcription, retranscription, and summarization endpoints."
        )
        desc.setObjectName("settingsDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        key_widget, self._api_key_input = _make_field(
            "API Key", current["api_key"], "Enter your API key", is_password=True
        )
        layout.addWidget(key_widget)

        layout.addStretch()
        return tab

    def _build_transcription_tab(self, current: dict[str, str]) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 20, 16, 16)

        desc = QLabel(
            "OpenAI-compatible transcription endpoint for real-time speech recognition."
        )
        desc.setObjectName("settingsDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        url_widget, self._url_input = _make_field(
            "Endpoint URL", current["asr_url"], "http://localhost:8178"
        )
        layout.addWidget(url_widget)

        layout.addStretch()
        return tab

    def _build_retranscription_tab(self, current: dict[str, str]) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 20, 16, 16)

        desc = QLabel(
            "Backend server for queued full-audio retranscription and meeting storage."
        )
        desc.setObjectName("settingsDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        backend_url_widget, self._backend_url_input = _make_field(
            "Backend URL", current["backend_url"], "http://localhost:5167"
        )
        layout.addWidget(backend_url_widget)

        layout.addStretch()
        return tab

    def _build_summarization_tab(self, current: dict[str, str]) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 20, 16, 16)

        desc = QLabel(
            "OpenAI-compatible chat completions endpoint for meeting summaries."
        )
        desc.setObjectName("settingsDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        llm_url_widget, self._llm_url_input = _make_field(
            "Endpoint URL", current["llm_url"], "http://localhost:11434"
        )
        layout.addWidget(llm_url_widget)

        # System prompt
        prompt_label = QLabel("System Prompt")
        prompt_label.setObjectName("settingsFieldLabel")
        layout.addWidget(prompt_label)

        prompt_hint = QLabel(
            "Custom instructions for the summarization LLM. "
            "Leave empty to use the built-in default."
        )
        prompt_hint.setObjectName("settingsDesc")
        prompt_hint.setWordWrap(True)
        layout.addWidget(prompt_hint)

        self._llm_prompt_input = QPlainTextEdit()
        self._llm_prompt_input.setPlaceholderText(
            "e.g. You are a meeting assistant. Summarize the transcript as bullet points..."
        )
        self._llm_prompt_input.setPlainText(current["llm_system_prompt"])
        self._llm_prompt_input.setFixedHeight(120)
        layout.addWidget(self._llm_prompt_input)

        layout.addStretch()
        return tab

    def _save(self) -> None:
        settings = QSettings("ZennoCall", "ZennoCall")
        settings.setValue("api_key", self._api_key_input.text().strip())
        settings.setValue("asr_url", self._url_input.text().strip())
        settings.setValue("llm_url", self._llm_url_input.text().strip())
        settings.setValue("llm_system_prompt", self._llm_prompt_input.toPlainText())
        settings.setValue("backend_url", self._backend_url_input.text().strip())
        self.accept()

    @staticmethod
    def get_settings() -> dict[str, str]:
        """Load saved settings with defaults."""
        settings = QSettings("ZennoCall", "ZennoCall")
        return {
            "api_key": settings.value("api_key", _DEFAULTS["api_key"]),
            "asr_url": settings.value("asr_url", _DEFAULTS["asr_url"]),
            "llm_url": settings.value("llm_url", _DEFAULTS["llm_url"]),
            "llm_system_prompt": settings.value("llm_system_prompt", _DEFAULTS["llm_system_prompt"]),
            "backend_url": settings.value(
                "backend_url", _DEFAULTS["backend_url"]
            ),
        }
