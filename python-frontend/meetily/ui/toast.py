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
    QSizePolicy,
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
    """Single auto-dismissing notification bubble.

    Automatically sizes its height based on the message text length
    and the available width.
    """

    _MAX_WIDTH = 360
    _MIN_WIDTH = 220

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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(10)

        # Icon
        icon_label = QLabel(_ICONS.get(toast_type, ""))
        icon_label.setObjectName(f"toastIcon{toast_type.value.title()}")
        icon_label.setFixedWidth(20)
        icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # Message — word-wrap is key
        self._msg_label = QLabel(message)
        self._msg_label.setObjectName("toastMessage")
        self._msg_label.setWordWrap(True)
        self._msg_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._msg_label, 1)

        # Close button
        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("toastCloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

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

    def apply_width_and_compute_height(self, width: int) -> int:
        """Set the toast width and return the correct height for its content.

        Uses QFontMetrics.boundingRect with TextWordWrap to measure how many
        lines the message needs at the given width, then adds layout margins.
        """
        self.setFixedWidth(width)

        margins = self.layout().contentsMargins()
        spacing = self.layout().spacing()
        # Available width for the text label = total - margins - icon - close - spacings
        text_w = (
            width
            - margins.left() - margins.right()
            - 20   # icon width
            - 22   # close button width
            - spacing * 2  # two gaps between three items
        )
        text_w = max(text_w, 60)

        fm = self._msg_label.fontMetrics()
        text_rect = fm.boundingRect(
            0, 0, text_w, 10000,
            int(Qt.TextFlag.TextWordWrap),
            self._msg_label.text(),
        )
        text_h = text_rect.height()

        # Total height = text height + vertical margins, with a sensible minimum
        total_h = text_h + margins.top() + margins.bottom()
        total_h = max(total_h, 40)  # minimum toast height

        self.setFixedHeight(total_h)
        return total_h

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
        self._margin = 12
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
        """Stack toasts from top-right, adapting width to window size."""
        pw = self._parent.width()

        # Toast width: up to MAX, but shrink if parent is narrow
        available = pw - self._margin * 2
        toast_w = min(Toast._MAX_WIDTH, max(Toast._MIN_WIDTH, available))

        x = pw - toast_w - self._margin
        x = max(self._margin, x)
        y = self._margin + 44  # below header bar

        for toast in self._toasts:
            h = toast.apply_width_and_compute_height(toast_w)
            toast.move(x, y)
            toast.raise_()
            y += h + self._gap
