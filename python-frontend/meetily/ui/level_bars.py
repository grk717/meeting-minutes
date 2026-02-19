"""Animated audio level bars widget.

Displays 3 vertical bars that animate based on real-time audio levels,
similar to the Meetily Tauri app's recording visualization.
"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Property, QTimer
from PySide6.QtGui import QColor, QPainter, QLinearGradient
from PySide6.QtWidgets import QWidget


def _level_color(level: float) -> QColor:
    """Map audio level (0-1) to green→yellow→red gradient."""
    if level < 0.4:
        # Green range
        return QColor(76, 217, 100)
    elif level < 0.7:
        # Yellow range
        t = (level - 0.4) / 0.3
        return QColor(
            int(76 + (255 - 76) * t),
            int(217 + (204 - 217) * t),
            int(100 + (0 - 100) * t),
        )
    else:
        # Red range
        t = (level - 0.7) / 0.3
        return QColor(
            255,
            int(204 - 204 * t),
            0,
        )


class LevelBarsWidget(QWidget):
    """Three animated vertical bars showing audio levels."""

    BAR_COUNT = 3
    BAR_SPACING = 6
    BAR_RADIUS = 4
    MIN_HEIGHT_FRAC = 0.15  # Minimum bar height as fraction

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(60, 80)

        # Bar heights as fractions (0.0 - 1.0)
        self._bar_values = [0.15, 0.15, 0.15]
        self._target_values = [0.15, 0.15, 0.15]

        # Smooth animation via timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_step)
        self._anim_timer.setInterval(30)  # ~33fps

        # Idle animation
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._idle_pulse)
        self._idle_timer.setInterval(600)
        self._idle_phase = 0

        self._is_active = False

    def set_active(self, active: bool) -> None:
        """Toggle between active (recording) and idle (pulsing) mode."""
        self._is_active = active
        if active:
            self._idle_timer.stop()
            self._anim_timer.start()
        else:
            self._anim_timer.stop()
            self._idle_timer.start()
            self._target_values = [0.15, 0.15, 0.15]
        self.update()

    def set_level(self, rms: float, peak: float) -> None:
        """Update bar targets from audio levels."""
        if not self._is_active:
            return

        # Amplify for visibility — audio RMS is typically 0.001-0.1
        rms = min(1.0, rms * 8.0)
        peak = min(1.0, peak * 5.0)

        # Create 3 bar values with slight variation for visual interest
        self._target_values = [
            max(self.MIN_HEIGHT_FRAC, rms * 0.85),
            max(self.MIN_HEIGHT_FRAC, peak * 0.95),
            max(self.MIN_HEIGHT_FRAC, rms * 0.75),
        ]

    def _animate_step(self) -> None:
        """Smooth interpolation toward target values."""
        changed = False
        for i in range(self.BAR_COUNT):
            diff = self._target_values[i] - self._bar_values[i]
            if abs(diff) > 0.001:
                # Fast attack, slow release
                speed = 0.35 if diff > 0 else 0.15
                self._bar_values[i] += diff * speed
                changed = True
        if changed:
            self.update()

    def _idle_pulse(self) -> None:
        """Gentle pulsing animation when idle."""
        self._idle_phase = (self._idle_phase + 1) % 6
        offsets = [0, 2, 4]  # Phase offsets for each bar
        for i in range(self.BAR_COUNT):
            phase = (self._idle_phase + offsets[i]) % 6
            if phase < 3:
                self._bar_values[i] = 0.15 + 0.08 * (phase / 2)
            else:
                self._bar_values[i] = 0.15 + 0.08 * ((6 - phase) / 2)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        total_spacing = self.BAR_SPACING * (self.BAR_COUNT - 1)
        bar_width = max(8, (w - total_spacing) // self.BAR_COUNT)

        # Center the bars
        total_width = bar_width * self.BAR_COUNT + total_spacing
        x_offset = (w - total_width) // 2

        for i in range(self.BAR_COUNT):
            bar_height = int(h * self._bar_values[i])
            bar_height = max(8, bar_height)

            x = x_offset + i * (bar_width + self.BAR_SPACING)
            y = h - bar_height

            # Gradient fill
            level = self._bar_values[i]
            color = _level_color(level) if self._is_active else QColor(100, 100, 120)

            gradient = QLinearGradient(x, y + bar_height, x, y)
            gradient.setColorAt(0.0, color.darker(130))
            gradient.setColorAt(1.0, color.lighter(120))

            painter.setBrush(gradient)
            painter.setPen(QColor(0, 0, 0, 0))
            painter.drawRoundedRect(x, y, bar_width, bar_height, self.BAR_RADIUS, self.BAR_RADIUS)

        painter.end()

    def stop(self) -> None:
        """Stop all timers (call before destruction)."""
        self._anim_timer.stop()
        self._idle_timer.stop()
