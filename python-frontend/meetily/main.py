"""Application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QFontDatabase, QFont, QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from meetily.ui.main_window import MainWindow
from meetily.ui.theme import DARK_THEME
from meetily.utils.paths import fonts_dir, icon_path


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
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


def main() -> None:
    setup_logging()
    log = logging.getLogger(__name__)
    log.info("Starting Meetily")

    app = QApplication(sys.argv)
    app.setApplicationName("Meetily")
    app.setOrganizationName("Meetily")

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
    main()
