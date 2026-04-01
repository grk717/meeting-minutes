"""Modern dark theme stylesheet for the application.

Design language inspired by Linear, Raycast, and Arc browser.
Uses a refined color system with muted blue-cyan tones, smooth borders,
and consistent spacing on an 8px grid.
"""

# ── Design Tokens ──
# Background layers (darkest to lightest):
#   bg-base:    #0a1018   (window/app background – dark blue-black)
#   bg-surface: #0e1620   (sidebar, panels)
#   bg-card:    #141e2a   (cards, elevated surfaces)
#   bg-hover:   #1c2a38   (hover states)
#   bg-input:   #0c1219   (input fields)
#
# Border:
#   border-subtle:  #172230   (dividers, card borders)
#   border-default: #1e3040   (input borders)
#   border-focus:   #3b82c4   (focus rings – muted blue)
#
# Text:
#   text-primary:   #e8ecf0   (headings, primary content)
#   text-secondary: #94a3b8   (body text, descriptions)
#   text-tertiary:  #5a7080   (captions, timestamps, placeholders)
#   text-disabled:  #2e4050   (disabled state)
#
# Accent:
#   accent:         #3b82c4   (primary actions, links – muted blue)
#   accent-hover:   #4a9ad6   (hover on accent – lighter blue)
#   accent-pressed: #2d6a9e   (pressed on accent – deeper blue)
#
# Semantic:
#   success:   #34b89a
#   warning:   #d4a032
#   error:     #d46464
#   info:      #5a9ec8

DARK_THEME = """
/* ================================================================
   GLOBAL FOUNDATION
   ================================================================ */

QMainWindow {
    background-color: #0a1018;
    color: #e8ecf0;
    font-family: "Inter", -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: transparent;
    font-family: "Inter", -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QLabel {
    color: #e8ecf0;
}

/* ================================================================
   SCROLL BARS
   ================================================================ */

QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 4px 2px;
    border: none;
}

QScrollBar::handle:vertical {
    background: rgba(200, 220, 240, 0.10);
    min-height: 32px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(200, 220, 240, 0.18);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    height: 0;
    background: transparent;
    border: none;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 2px 4px;
    border: none;
}

QScrollBar::handle:horizontal {
    background: rgba(200, 220, 240, 0.10);
    min-width: 32px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: rgba(200, 220, 240, 0.18);
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    width: 0;
    background: transparent;
    border: none;
}

/* ================================================================
   TYPOGRAPHY & LABELS
   ================================================================ */

#appTitle {
    font-size: 20px;
    font-weight: 700;
    color: #e8ecf0;
    padding: 0;
    margin: 0;
    letter-spacing: -0.5px;
}

#appSubtitle {
    font-size: 12px;
    color: #5a7080;
    padding: 0;
    margin: 0;
    letter-spacing: 0.3px;
}

#durationLabel {
    font-size: 36px;
    font-weight: 200;
    color: #e8ecf0;
    font-family: "JetBrains Mono", "SF Mono", "Cascadia Mono", "Consolas", monospace;
    letter-spacing: 2px;
}

#statusLabel {
    font-size: 12px;
    color: #5a7080;
    letter-spacing: 0.2px;
}

#levelLabel {
    font-size: 10px;
    color: #3e5868;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
}

#savedLabel {
    font-size: 12px;
    color: #34b89a;
    padding: 6px 0;
}

#deviceLabel {
    font-size: 12px;
    color: #94a3b8;
    font-weight: 500;
}

/* ================================================================
   GROUP BOXES (Section containers)
   ================================================================ */

QGroupBox {
    background-color: #0e1620;
    border: 1px solid #172230;
    border-radius: 12px;
    margin-top: 16px;
    padding: 20px 16px 16px 16px;
    font-weight: 600;
    font-size: 13px;
    color: #94a3b8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 14px;
    color: #5a7080;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 700;
}

/* ================================================================
   INPUT FIELDS
   ================================================================ */

QLineEdit {
    background-color: #0c1219;
    border: 1px solid #1e3040;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e8ecf0;
    font-size: 13px;
    selection-background-color: #3b82c4;
    selection-color: #ffffff;
}

QLineEdit:focus {
    border-color: #3b82c4;
    background-color: #0e1822;
}

QLineEdit:disabled {
    background-color: #0a1018;
    color: #2e4050;
    border-color: #141e2a;
}

QLineEdit::placeholder {
    color: #3e5868;
}

/* ================================================================
   COMBO BOXES
   ================================================================ */

QComboBox {
    background-color: #0c1219;
    border: 1px solid #1e3040;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e8ecf0;
    font-size: 13px;
    min-height: 18px;
}

QComboBox:hover {
    border-color: #284058;
    background-color: #0e1822;
}

QComboBox:focus {
    border-color: #3b82c4;
}

QComboBox:disabled {
    background-color: #0a1018;
    color: #2e4050;
    border-color: #141e2a;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
    padding-right: 4px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #5a7080;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #141e2a;
    border: 1px solid #1e3040;
    border-radius: 8px;
    color: #e8ecf0;
    selection-background-color: #3b82c4;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    padding: 6px 12px;
    border-radius: 4px;
    min-height: 24px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #1c2a38;
}

/* ================================================================
   CHECKBOXES
   ================================================================ */

QCheckBox {
    color: #94a3b8;
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid #1e3040;
    background-color: #0c1219;
}

QCheckBox::indicator:checked {
    background-color: #3b82c4;
    border-color: #3b82c4;
}

QCheckBox::indicator:hover {
    border-color: #3b82c4;
}

QCheckBox:disabled {
    color: #2e4050;
}

QCheckBox::indicator:disabled {
    background-color: #0a1018;
    border-color: #141e2a;
}

/* ================================================================
   BUTTONS — all buttons share the same base style
   ================================================================ */

QPushButton {
    background-color: #141e2e;
    color: #6e8494;
    border: 1px solid #1e3040;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.2px;
}

QPushButton:hover {
    background-color: #1c2a38;
    color: #a0b4c4;
    border-color: #284058;
}

QPushButton:pressed {
    background-color: #0e1620;
    color: #6e8494;
    border-color: #1e3040;
}

QPushButton:disabled {
    background-color: #0e1822;
    color: #2e4050;
    border: 1px solid #141e2a;
}

/* Record button — muted blue fill, the one accent exception */
#recordBtn {
    background-color: #3b82c4;
    color: #ffffff;
    border: none;
    min-width: 160px;
    border-radius: 10px;
}

#recordBtn:hover {
    background-color: #4a9ad6;
    color: #ffffff;
    border: none;
}

#recordBtn:pressed {
    background-color: #2d6a9e;
    color: #ffffff;
    border: none;
}

/* Stop button — muted red fill */
#stopBtn {
    background-color: #c44040;
    color: #ffffff;
    border: none;
    min-width: 160px;
    border-radius: 10px;
}

#stopBtn:hover {
    background-color: #d46464;
    color: #ffffff;
    border: none;
}

#stopBtn:pressed {
    background-color: #a83232;
    color: #ffffff;
    border: none;
}

/* Size-only overrides (colors inherited from base QPushButton) */
#pauseBtn {
    min-width: 80px;
}

#refreshBtn {
    font-size: 11px;
    font-weight: 500;
    padding: 5px 12px;
    border-radius: 6px;
}

#settingsBtn {
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    min-width: 0;
}

#generateBtn {
    padding: 8px 20px;
}

/* ================================================================
   SPLITTER
   ================================================================ */

QSplitter::handle {
    background: transparent;
    width: 1px;
}

#contentSplitter::handle {
    background-color: #172230;
    border-left: 1px solid #141e2a;
    border-right: 1px solid #141e2a;
    width: 9px;
    margin: 12px 0;
    border-radius: 4px;
}

#contentSplitter::handle:hover {
    background-color: #1e3040;
}

#contentSplitter::handle:pressed {
    background-color: #3b82c4;
}

/* ================================================================
   SIDEBAR
   ================================================================ */

#sidebar {
    background-color: #0c1219;
    border-right: 1px solid #172230;
}

#sidebarTitle {
    font-size: 11px;
    font-weight: 600;
    color: #3e5868;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

#sidebarSearch {
    background-color: #0e1620;
    border: 1px solid #172230;
    border-radius: 8px;
    padding: 7px 12px 7px 30px;
    color: #e8ecf0;
    font-size: 12px;
}

#sidebarSearch:focus {
    border-color: #3b82c4;
    background-color: #101c28;
}

#sidebarSearch::placeholder {
    color: #3e5868;
}

#sidebarNewBtn {
    padding: 8px 0;
    font-size: 12px;
    min-width: 0;
}

/* Meeting list item */
#sidebarItemName {
    font-size: 13px;
    color: #a0b4c4;
    font-weight: 500;
}

#sidebarItemMeta {
    font-size: 11px;
    color: #3e5868;
}

#sidebarItemPreview {
    font-size: 11px;
    color: #3e5868;
}

#sidebarDeleteBtn {
    background-color: transparent;
    color: #3e5868;
    border: none;
    font-size: 12px;
    font-weight: bold;
    padding: 0;
    min-width: 0;
    border-radius: 4px;
}

#sidebarDeleteBtn:hover {
    color: #d46464;
    background-color: rgba(212, 100, 100, 0.1);
}

#sidebarScroll {
    background-color: transparent;
    border: none;
}

/* Selected sidebar item uses dynamic property */
MeetingListItem[selected="true"] {
    background-color: #141e30;
    border-radius: 6px;
}

MeetingListItem[selected="true"] #sidebarItemName {
    color: #d0dce8;
}

MeetingListItem:hover {
    background-color: #101a24;
    border-radius: 6px;
}

/* ================================================================
   MEETING DETAIL BAR
   ================================================================ */

#meetingDetailBar {
    background-color: #0e1620;
    border-bottom: 1px solid #172230;
    padding: 6px 8px;
}

#meetingDetailTitle {
    font-size: 15px;
    font-weight: 600;
    color: #e8ecf0;
    letter-spacing: -0.2px;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 2px 4px;
}

#meetingDetailTitle:focus {
    border-color: #3b82c4;
    background-color: #0c1219;
}

#meetingDetailMeta {
    font-size: 11px;
    color: #5a7080;
}

#detailActionBtn,
#detailPrimaryBtn {
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    min-width: 0;
}

#detailActionBtn {
    font-weight: 500;
}

/* ================================================================
   TRANSCRIPT PANEL
   ================================================================ */

#transcriptPanel {
    background-color: #0e1620;
    border: 1px solid #172230;
    border-radius: 12px;
}

#transcriptHeader {
    font-size: 10px;
    font-weight: 700;
    color: #5a7080;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    padding: 0;
}

#transcriptSegment {
    font-size: 13px;
    color: #b8c8d8;
    line-height: 1.6;
    padding: 6px 0;
}

#transcriptTimestamp {
    font-size: 10px;
    color: #3e5868;
    font-family: "JetBrains Mono", "SF Mono", "Cascadia Mono", "Consolas", monospace;
    font-weight: 500;
}

#transcriptSpeaker {
    font-size: 11px;
    color: #3b82c4;
    font-weight: 600;
}

#transcriptScroll {
    background-color: transparent;
    border: none;
}

/* ================================================================
   SUMMARY PANEL
   ================================================================ */

#summaryPanel {
    background-color: #0e1620;
    border: 1px solid #172230;
    border-radius: 12px;
}

#summaryHeader {
    font-size: 10px;
    font-weight: 700;
    color: #5a7080;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

#summaryText {
    font-size: 13px;
    color: #b8c8d8;
    line-height: 1.7;
    padding: 8px 0;
}

#summaryPlaceholder {
    font-size: 12px;
    color: #3e5868;
    font-style: italic;
}

#summaryScroll {
    background-color: transparent;
    border: none;
}

/* ================================================================
   RETRANSCRIBE WIDGET
   ================================================================ */

#retranscribeWidget {
    background-color: #0e1620;
    border-bottom: 1px solid #172230;
    padding: 8px;
}

#retranscribeStatus {
    font-size: 12px;
    color: #94a3b8;
}

#retranscribeProgress {
    background-color: #141e2a;
    border-radius: 3px;
}

#retranscribeProgress::chunk {
    background-color: #3b82c4;
    border-radius: 3px;
}

/* ================================================================
   SPEAKER MAPPING PANEL
   ================================================================ */

#speakerPanel {
    background-color: #0e1620;
    border-bottom: 1px solid #172230;
    padding: 6px 12px;
}

#speakerPanelTitle {
    font-size: 10px;
    font-weight: 700;
    color: #5a7080;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

#speakerLabel {
    font-size: 12px;
    color: #5a7080;
    font-weight: 500;
}

#speakerInput {
    background-color: #0c1219;
    border: 1px solid #1e3040;
    border-radius: 6px;
    padding: 5px 8px;
    color: #e8ecf0;
    font-size: 12px;
}

#speakerInput:focus {
    border-color: #3b82c4;
}

#speakerApplyBtn {
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 12px;
    min-width: 0;
}

/* ================================================================
   TOAST NOTIFICATIONS
   ================================================================ */

#toast {
    border-radius: 10px;
    border: 1px solid #1e3040;
    padding: 0px;
}

#toast[toastType="success"] {
    background-color: rgba(52, 184, 154, 0.18);
    border-color: rgba(52, 184, 154, 0.35);
}

#toast[toastType="error"] {
    background-color: rgba(212, 100, 100, 0.18);
    border-color: rgba(212, 100, 100, 0.35);
}

#toast[toastType="warning"] {
    background-color: rgba(212, 160, 50, 0.18);
    border-color: rgba(212, 160, 50, 0.35);
}

#toast[toastType="info"] {
    background-color: rgba(90, 158, 200, 0.18);
    border-color: rgba(90, 158, 200, 0.35);
}

#toastIconSuccess {
    color: #34b89a;
    font-size: 16px;
    font-weight: bold;
}

#toastIconError {
    color: #d46464;
    font-size: 16px;
    font-weight: bold;
}

#toastIconWarning {
    color: #d4a032;
    font-size: 16px;
    font-weight: bold;
}

#toastIconInfo {
    color: #5a9ec8;
    font-size: 16px;
    font-weight: bold;
}

#toastMessage {
    color: #e8ecf0;
    font-size: 13px;
    font-weight: 500;
}

#toastCloseBtn {
    background-color: transparent;
    color: #5a7080;
    border: none;
    font-size: 13px;
    padding: 2px;
    min-width: 0;
    border-radius: 4px;
}

#toastCloseBtn:hover {
    color: #e8ecf0;
    background-color: rgba(200, 220, 240, 0.1);
}

/* ================================================================
   SETTINGS DIALOG
   ================================================================ */

QDialog {
    background-color: #0a1018;
    color: #e8ecf0;
}

#settingsSection {
    font-size: 11px;
    font-weight: 700;
    color: #3b82c4;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 4px 0;
}

#settingsDesc {
    font-size: 12px;
    color: #5a7080;
    line-height: 1.5;
}

#settingsFieldLabel {
    font-size: 12px;
    color: #94a3b8;
    font-weight: 500;
}

QDialogButtonBox QPushButton {
    min-width: 90px;
}

/* ================================================================
   MESSAGE BOXES
   ================================================================ */

QMessageBox {
    background-color: #0e1620;
}

QMessageBox QLabel {
    color: #e8ecf0;
    font-size: 13px;
}

QMessageBox QPushButton {
    min-width: 80px;
    padding: 8px 16px;
}

/* ================================================================
   RECORDING SECTION (within main content)
   ================================================================ */

#recordingSection {
    background-color: #0e1620;
    border: 1px solid #172230;
    border-radius: 12px;
}

#recordingTitle {
    font-size: 10px;
    font-weight: 700;
    color: #5a7080;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

#meetingNameInput {
    background-color: #0c1219;
    border: 1px solid #1e3040;
    border-radius: 8px;
    padding: 10px 14px;
    color: #e8ecf0;
    font-size: 14px;
    font-weight: 500;
}

#meetingNameInput:focus {
    border-color: #3b82c4;
    background-color: #0e1822;
}

/* ================================================================
   TAB BAR (for transcript/summary switching)
   ================================================================ */

#tabBar {
    background-color: transparent;
}

#tabActive {
    background-color: #141e2a;
    color: #e8ecf0;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
    min-width: 0;
}

#tabInactive {
    background-color: transparent;
    color: #5a7080;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 500;
    min-width: 0;
}

#tabInactive:hover {
    color: #94a3b8;
    background-color: rgba(200, 220, 240, 0.03);
}

/* ================================================================
   SECTION DIVIDER
   ================================================================ */

#divider {
    background-color: #172230;
    max-height: 1px;
    min-height: 1px;
}
"""
