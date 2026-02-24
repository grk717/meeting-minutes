"""Auto-dismissing toast notifications for user feedback."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QPropertyAnimation, QTimer, Qt, QEasingCurve
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QWidget


class ToastType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


_ICONS = {
    ToastType.SUCCESS: "\u2713",  # ✓
    ToastType.ERROR: "\u2717",    # ✗
    ToastType.WARNING: "\u26A0",  # ⚠
    ToastType.INFO: "\u2139",     # ℹ
}


class Toast(QFrame):
    """Single auto-dismissing notification bubble."""

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
        self.setFixedWidth(340)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        # Icon
        icon_label = QLabel(_ICONS.get(toast_type, ""))
        icon_label.setObjectName(f"toastIcon{toast_type.value.title()}")
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)

        # Message
        msg_label = QLabel(message)
        msg_label.setObjectName("toastMessage")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label, 1)

        # Close button
        close_btn = QPushButton("\u2715")  # ✕
        close_btn.setObjectName("toastCloseBtn")
        close_btn.setFixedSize(20, 20)
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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def _dismiss(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        self._timer.stop()

        # Fade out via opacity effect
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(200)
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
        self._gap = 8

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
        """Stack toasts from top-right of the parent widget."""
        parent_rect = self._parent.rect()
        x = parent_rect.right() - 340 - self._margin
        y = self._margin

        for toast in self._toasts:
            toast.move(x, y)
            toast.raise_()
            y += toast.sizeHint().height() + self._gap
