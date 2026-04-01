"""Polished auto-dismissing toast notifications for user feedback.

Redesigned with refined colors, smoother animations, and modern styling.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QPropertyAnimation, QTimer, Qt, QEasingCurve
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class ToastType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


_ICONS = {
    ToastType.SUCCESS: "\u2713",  # check
    ToastType.ERROR: "\u2717",    # x
    ToastType.WARNING: "\u26A0",  # warning
    ToastType.INFO: "\u2139",     # info
}


class Toast(QFrame):
    """Single auto-dismissing notification bubble."""

    # Toast sizing constraints
    _MAX_WIDTH = 360
    _MIN_WIDTH = 200

    def __init__(
        self,
        message: str,
        toast_type: ToastType = ToastType.INFO,
        duration_ms: int = 4000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setProperty("toastType", toast_type.value)
        self.setMaximumWidth(self._MAX_WIDTH)
        self.setMinimumWidth(self._MIN_WIDTH)

        # Horizontal margins: icon(22) + spacing(12)*2 + close(24) + margins(16+12)
        self._chrome_width = 22 + 12 + 12 + 24 + 16 + 12  # = 98

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(12)

        # Icon
        icon_label = QLabel(_ICONS.get(toast_type, ""))
        icon_label.setObjectName(f"toastIcon{toast_type.value.title()}")
        icon_label.setFixedWidth(22)
        layout.addWidget(icon_label)

        # Message
        self._msg_label = QLabel(message)
        self._msg_label.setObjectName("toastMessage")
        self._msg_label.setWordWrap(True)
        self._msg_label.setMinimumHeight(20)
        layout.addWidget(self._msg_label, 1)

        # Close button
        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("toastCloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)

        # Opacity effect for fade-out animation
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)

        # Auto-dismiss timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(duration_ms)
        self._timer.timeout.connect(self._dismiss)

        self._dismissed = False
        self._manager: ToastManager | None = None

    def compute_height_for_width(self, w: int) -> int:
        """Calculate the correct total height given a fixed width."""
        text_width = w - self._chrome_width
        text_height = self._msg_label.fontMetrics().boundingRect(
            0, 0, text_width, 0,
            Qt.TextFlag.TextWordWrap, self._msg_label.text(),
        ).height()
        # Vertical margins (12 top + 12 bottom) + at least 20px for single line
        return max(text_height, 20) + 24

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def _dismiss(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        self._timer.stop()

        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(250)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InQuad)
        anim.finished.connect(self._on_fade_done)
        anim.start()

    def _on_fade_done(self) -> None:
        if self._manager:
            self._manager._remove_toast(self)
        self.deleteLater()


class ToastManager:
    """Manages stacking of toast notifications in the parent window."""

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._toasts: list[Toast] = []
        self._margin = 16
        self._gap = 6

    def show_toast(
        self,
        message: str,
        toast_type: ToastType = ToastType.INFO,
        duration_ms: int = 4000,
    ) -> None:
        toast = Toast(message, toast_type, duration_ms, self._parent)
        toast._manager = self
        self._toasts.append(toast)
        toast.show()
        self._reposition()

    def success(self, message: str, duration_ms: int = 3000) -> None:
        self.show_toast(message, ToastType.SUCCESS, duration_ms)

    def error(self, message: str, duration_ms: int = 6000) -> None:
        self.show_toast(message, ToastType.ERROR, duration_ms)

    def warning(self, message: str, duration_ms: int = 5000) -> None:
        self.show_toast(message, ToastType.WARNING, duration_ms)

    def info(self, message: str, duration_ms: int = 4000) -> None:
        self.show_toast(message, ToastType.INFO, duration_ms)

    def _remove_toast(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
            self._reposition()

    def _reposition(self) -> None:
        """Stack toasts from top-right of the parent widget, adapting to window size."""
        parent_rect = self._parent.rect()
        # Calculate toast width: up to MAX_WIDTH but capped at parent width minus margins
        available_width = parent_rect.width() - self._margin * 2
        toast_width = min(Toast._MAX_WIDTH, max(Toast._MIN_WIDTH, available_width))

        x = parent_rect.right() - toast_width - self._margin
        # Ensure x doesn't go negative on very small windows
        x = max(self._margin, x)
        y = self._margin + 44  # offset below header bar

        for toast in self._toasts:
            toast.setFixedWidth(toast_width)
            h = toast.compute_height_for_width(toast_width)
            toast.setFixedHeight(h)
            toast.move(x, y)
            toast.raise_()
            y += h + self._gap
