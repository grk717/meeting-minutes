"""Modern animated audio level visualizer.

Displays smooth vertical bars with gradient fills and glow effects,
providing a visually impressive recording indicator.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QPen
from PySide6.QtWidgets import QWidget


class LevelBarsWidget(QWidget):
    """Animated vertical bars showing audio levels with modern aesthetics."""

    BAR_COUNT = 5
    BAR_SPACING = 4
    BAR_RADIUS = 3
    MIN_HEIGHT_FRAC = 0.08

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(80, 80)

        # Bar heights as fractions (0.0 - 1.0)
        self._bar_values = [self.MIN_HEIGHT_FRAC] * self.BAR_COUNT
        self._target_values = [self.MIN_HEIGHT_FRAC] * self.BAR_COUNT

        # Smooth animation via timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_step)
        self._anim_timer.setInterval(25)  # 40fps

        # Idle animation
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._idle_pulse)
        self._idle_timer.setInterval(50)
        self._idle_phase = 0.0

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
            self._target_values = [self.MIN_HEIGHT_FRAC] * self.BAR_COUNT
        self.update()

    def set_level(self, rms: float, peak: float) -> None:
        """Update bar targets from audio levels."""
        if not self._is_active:
            return

        # Amplify for visibility
        rms = min(1.0, rms * 8.0)
        peak = min(1.0, peak * 5.0)

        # Create bar values with variation for visual interest
        center_val = max(self.MIN_HEIGHT_FRAC, peak * 0.95)
        mid_val = max(self.MIN_HEIGHT_FRAC, rms * 0.85)
        outer_val = max(self.MIN_HEIGHT_FRAC, rms * 0.65)

        if self.BAR_COUNT == 5:
            self._target_values = [
                outer_val * 0.8,
                mid_val * 0.9,
                center_val,
                mid_val * 0.9,
                outer_val * 0.8,
            ]
        else:
            for i in range(self.BAR_COUNT):
                dist = abs(i - (self.BAR_COUNT - 1) / 2.0) / ((self.BAR_COUNT - 1) / 2.0)
                self._target_values[i] = max(
                    self.MIN_HEIGHT_FRAC,
                    center_val * (1.0 - dist * 0.4),
                )

    def _animate_step(self) -> None:
        """Smooth interpolation toward target values."""
        changed = False
        for i in range(self.BAR_COUNT):
            diff = self._target_values[i] - self._bar_values[i]
            if abs(diff) > 0.001:
                speed = 0.4 if diff > 0 else 0.12
                self._bar_values[i] += diff * speed
                changed = True
        if changed:
            self.update()

    def _idle_pulse(self) -> None:
        """Smooth sine-wave pulsing animation when idle."""
        self._idle_phase += 0.06
        if self._idle_phase > 2 * math.pi * 100:
            self._idle_phase = 0.0

        for i in range(self.BAR_COUNT):
            offset = i * 0.6
            val = 0.08 + 0.06 * math.sin(self._idle_phase + offset)
            self._bar_values[i] = val
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        total_spacing = self.BAR_SPACING * (self.BAR_COUNT - 1)
        bar_width = max(6, (w - total_spacing) // self.BAR_COUNT)

        # Center the bars
        total_width = bar_width * self.BAR_COUNT + total_spacing
        x_offset = (w - total_width) // 2

        for i in range(self.BAR_COUNT):
            bar_height = int(h * self._bar_values[i])
            bar_height = max(6, min(h - 2, bar_height))

            x = x_offset + i * (bar_width + self.BAR_SPACING)
            y = h - bar_height

            level = self._bar_values[i]

            if self._is_active:
                # Active: muted blue to cyan gradient
                color_bottom = QColor(59, 130, 196)    # muted blue
                color_top = QColor(58, 166, 185)        # muted teal

                if level > 0.6:
                    # High levels get brighter cyan
                    t = (level - 0.6) / 0.4
                    color_top = QColor(
                        int(58 + (74 - 58) * t),
                        int(166 + (194 - 166) * t),
                        int(185 + (214 - 185) * t),
                    )
            else:
                # Idle: subtle muted bars
                color_bottom = QColor(28, 42, 56)
                color_top = QColor(36, 54, 72)

            gradient = QLinearGradient(x, y + bar_height, x, y)
            gradient.setColorAt(0.0, color_bottom)
            gradient.setColorAt(1.0, color_top)

            painter.setPen(QPen(QColor(0, 0, 0, 0)))
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                x, y, bar_width, bar_height,
                self.BAR_RADIUS, self.BAR_RADIUS,
            )

            # Subtle glow effect on active bars with high levels
            if self._is_active and level > 0.3:
                glow_alpha = int(25 * min(1.0, level))
                glow_color = QColor(59, 130, 196, glow_alpha)
                painter.setPen(QPen(glow_color, 2))
                painter.setBrush(QColor(0, 0, 0, 0))
                painter.drawRoundedRect(
                    x - 1, y - 1, bar_width + 2, bar_height + 2,
                    self.BAR_RADIUS + 1, self.BAR_RADIUS + 1,
                )

        painter.end()

    def stop(self) -> None:
        """Stop all timers (call before destruction)."""
        self._anim_timer.stop()
        self._idle_timer.stop()
