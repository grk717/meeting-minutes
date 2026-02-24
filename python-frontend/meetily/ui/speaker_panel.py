"""Inline panel for mapping speaker IDs to human-readable names."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SpeakerMappingPanel(QWidget):
    """Compact inline panel showing one input per detected speaker.

    Layout (wraps for many speakers):
        [Speaker 0: [______]] [Speaker 1: [______]] ... [Apply]

    Hidden when there are no speakers to map.
    """

    mapping_applied = Signal(dict)  # {speaker_id_str: name}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("speakerPanel")

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(8, 6, 8, 6)
        self._outer.setSpacing(6)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        title = QLabel("Speaker Names")
        title.setObjectName("speakerPanelTitle")
        header_row.addWidget(title)
        header_row.addStretch()

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setObjectName("speakerApplyBtn")
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setFixedWidth(70)
        self._apply_btn.clicked.connect(self._on_apply)
        header_row.addWidget(self._apply_btn)

        self._outer.addLayout(header_row)

        # Inputs container (rebuilt when speakers change)
        self._inputs_widget = QWidget()
        self._inputs_layout = QHBoxLayout(self._inputs_widget)
        self._inputs_layout.setContentsMargins(0, 0, 0, 0)
        self._inputs_layout.setSpacing(12)
        self._outer.addWidget(self._inputs_widget)

        self._inputs: dict[str, QLineEdit] = {}  # speaker_id -> QLineEdit
        self.setVisible(False)

    def set_speakers(
        self, speaker_ids: list[str], current_names: dict[str, str]
    ) -> None:
        """Populate the panel with input fields for each speaker ID."""
        # Clear old inputs
        self._clear_inputs()
        self._inputs.clear()

        if not speaker_ids:
            self.setVisible(False)
            return

        # Sort speaker IDs numerically if possible
        def sort_key(sid: str) -> tuple:
            try:
                return (0, int(sid))
            except ValueError:
                return (1, sid)

        for sid in sorted(speaker_ids, key=sort_key):
            pair = QHBoxLayout()
            pair.setSpacing(4)

            label = QLabel(f"Speaker {sid}:")
            label.setObjectName("speakerLabel")
            pair.addWidget(label)

            line = QLineEdit()
            line.setObjectName("speakerInput")
            line.setPlaceholderText(f"Speaker {sid}")
            line.setFixedWidth(120)
            # Pre-fill with saved name
            saved = current_names.get(str(sid), "")
            if saved:
                line.setText(saved)
            pair.addWidget(line)

            self._inputs_layout.addLayout(pair)
            self._inputs[str(sid)] = line

        self._inputs_layout.addStretch()
        self.setVisible(True)

    def get_mapping(self) -> dict[str, str]:
        """Return current {speaker_id: name} mapping (only non-empty)."""
        return {
            sid: line.text().strip()
            for sid, line in self._inputs.items()
            if line.text().strip()
        }

    def reset(self) -> None:
        """Hide panel and clear state."""
        self._clear_inputs()
        self._inputs.clear()
        self.setVisible(False)

    def _on_apply(self) -> None:
        self.mapping_applied.emit(self.get_mapping())

    def _clear_inputs(self) -> None:
        """Remove all child widgets/layouts from the inputs layout."""
        while self._inputs_layout.count():
            item = self._inputs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Recursively delete layout children
                sub = item.layout()
                while sub.count():
                    child = sub.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
