"""Dark theme stylesheet for the application."""

DARK_THEME = """
/* ── Global ── */
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

/* ── Group boxes ── */
QGroupBox {
    background-color: #16213e;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    margin-top: 14px;
    padding: 18px 14px 14px 14px;
    font-weight: 600;
    font-size: 13px;
    color: #a0a0c0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 12px;
    color: #8888aa;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Labels ── */
#appTitle {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
    padding: 0;
    margin: 0;
}

#appSubtitle {
    font-size: 13px;
    color: #7777aa;
    padding: 0;
    margin: 0;
}

#durationLabel {
    font-size: 32px;
    font-weight: 300;
    color: #ffffff;
    font-family: "SF Mono", "Cascadia Mono", "Consolas", monospace;
}

#statusLabel {
    font-size: 13px;
    color: #8888aa;
}

#levelLabel {
    font-size: 11px;
    color: #666688;
}

#savedLabel {
    font-size: 12px;
    color: #4cd964;
    padding: 4px;
}

#deviceLabel {
    font-size: 13px;
    color: #b0b0cc;
    font-weight: 500;
}

/* ── Inputs ── */
QLineEdit {
    background-color: #0f1a30;
    border: 1px solid #2a2a4a;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 13px;
    selection-background-color: #4c6ef5;
}

QLineEdit:focus {
    border-color: #4c6ef5;
}

QLineEdit:disabled {
    background-color: #141428;
    color: #555577;
}

/* ── Combo boxes ── */
QComboBox {
    background-color: #0f1a30;
    border: 1px solid #2a2a4a;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 13px;
    min-height: 20px;
}

QComboBox:hover {
    border-color: #3a3a6a;
}

QComboBox:disabled {
    background-color: #141428;
    color: #555577;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #7777aa;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #16213e;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    color: #e0e0e0;
    selection-background-color: #4c6ef5;
    padding: 4px;
}

/* ── Buttons ── */
QPushButton {
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}

#recordBtn {
    background-color: #4c6ef5;
    color: #ffffff;
    min-width: 160px;
}

#recordBtn:hover {
    background-color: #5c7cff;
}

#recordBtn:pressed {
    background-color: #3b5bdb;
}

#stopBtn {
    background-color: #e03131;
    color: #ffffff;
    min-width: 160px;
}

#stopBtn:hover {
    background-color: #f03e3e;
}

#stopBtn:pressed {
    background-color: #c92a2a;
}

#pauseBtn {
    background-color: #2a2a4a;
    color: #c0c0e0;
    min-width: 100px;
}

#pauseBtn:hover {
    background-color: #3a3a5a;
}

#refreshBtn {
    background-color: transparent;
    color: #7777aa;
    font-size: 11px;
    font-weight: 400;
    padding: 4px 12px;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
}

#refreshBtn:hover {
    background-color: #1a1a3e;
    color: #9999bb;
}

QPushButton:disabled {
    background-color: #1a1a3e;
    color: #444466;
}

/* ── Scrollbar ── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #3a3a5a;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* ── Message box ── */
QMessageBox {
    background-color: #1a1a2e;
}

QMessageBox QLabel {
    color: #e0e0e0;
}

QMessageBox QPushButton {
    background-color: #2a2a4a;
    color: #e0e0e0;
    min-width: 80px;
    padding: 8px 16px;
}

QMessageBox QPushButton:hover {
    background-color: #3a3a5a;
}
"""
