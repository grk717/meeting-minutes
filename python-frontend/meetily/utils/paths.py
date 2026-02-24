"""Resolve bundled resource paths for both development and frozen (PyInstaller) mode."""

from __future__ import annotations

import sys
from pathlib import Path


def _bundle_dir() -> Path:
    """Return the base directory for bundled resources.

    In frozen mode (PyInstaller one-dir), returns sys._MEIPASS / "meetily".
    In development, returns the meetily/ package root.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "meetily"
    return Path(__file__).resolve().parent.parent


def fonts_dir() -> Path:
    """Return the path to the bundled fonts directory."""
    return _bundle_dir() / "ui" / "fonts"


def icon_path() -> Path:
    """Return the path to the app icon (PNG)."""
    return _bundle_dir() / "resources" / "icon.png"
