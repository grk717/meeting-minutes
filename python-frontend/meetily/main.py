"""Application entry point.

Launch with --debug or MEETILY_DEBUG=1 to enable:
  - tracemalloc memory tracking
  - DebugMonitor with periodic snapshots
  - DEBUG-level logging
  - faulthandler crash tracebacks to ~/Documents/ZennoCall/crash_logs/
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from PySide6.QtGui import QFontDatabase, QFont, QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from meetily.ui.main_window import MainWindow
from meetily.ui.theme import DARK_THEME
from meetily.utils.paths import fonts_dir, icon_path


def setup_logging(debug: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_bundled_fonts() -> None:
    """Load Inter and JetBrains Mono from the bundled fonts directory."""
    fdir = fonts_dir()
    for font_file in fdir.glob("*.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            logging.getLogger(__name__).info(
                "Loaded font: %s -> %s", font_file.name, families
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZennoCall — AI Meeting Assistant")
    parser.add_argument(
        "--debug",
        action="store_true",
        default=bool(os.environ.get("MEETILY_DEBUG")),
        help="Enable debug mode: verbose logging, memory tracking, crash diagnostics",
    )
    # Qt passes its own args; use parse_known_args to avoid conflicts
    args, _ = parser.parse_known_args()
    return args


def main() -> None:
    args = parse_args()

    # Set env var so other modules (MainWindow) can check it
    if args.debug:
        os.environ["MEETILY_DEBUG"] = "1"

    setup_logging(debug=args.debug)
    log = logging.getLogger(__name__)
    log.info("Starting ZennoCall%s", " (DEBUG MODE)" if args.debug else "")

    # Start memory tracing early in debug mode
    if args.debug:
        import tracemalloc
        tracemalloc.start()
        log.info("tracemalloc enabled")

    app = QApplication(sys.argv)
    app.setApplicationName("ZennoCall")
    app.setOrganizationName("ZennoCall")

    # Set application icon
    _icon = icon_path()
    if _icon.exists():
        app.setWindowIcon(QIcon(str(_icon)))

    # Enable high-DPI scaling
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Load bundled fonts (Inter, JetBrains Mono)
    _load_bundled_fonts()

    # Set Inter as the default application font
    default_font = QFont("Inter")
    default_font.setPixelSize(13)
    default_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(default_font)

    # Apply dark theme
    app.setStyleSheet(DARK_THEME)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    # Required for multiprocessing on Windows (PyInstaller and spawn mode)
    import multiprocessing
    multiprocessing.freeze_support()
    main()
