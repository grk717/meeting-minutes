"""Modern dark theme stylesheet for the application.

Design language inspired by Linear, Raycast, and Arc browser.
Uses a refined color system with subtle gradients, smooth borders,
and consistent spacing on an 8px grid.
"""

# ── Design Tokens ──
# Background layers (darkest to lightest):
#   bg-base:    #0d0d14   (window/app background)
#   bg-surface: #13131f   (sidebar, panels)
#   bg-card:    #1a1a2a   (cards, elevated surfaces)
#   bg-hover:   #222238   (hover states)
#   bg-input:   #0f0f1a   (input fields)
#
# Border:
#   border-subtle:  #1e1e32   (dividers, card borders)
#   border-default: #2a2a42   (input borders)
#   border-focus:   #6366f1   (focus rings)
#
# Text:
#   text-primary:   #f0f0f5   (headings, primary content)
#   text-secondary: #a0a0b8   (body text, descriptions)
#   text-tertiary:  #6b6b80   (captions, timestamps, placeholders)
#   text-disabled:  #3a3a4e   (disabled state)
#
# Accent:
#   accent:         #6366f1   (primary actions, links)
#   accent-hover:   #7c7ff7   (hover on accent)
#   accent-pressed: #4f46e5   (pressed on accent)
#
# Semantic:
#   success:   #34d399
#   warning:   #fbbf24
#   error:     #f87171
#   info:      #60a5fa

DARK_THEME = """
/* ================================================================
   GLOBAL FOUNDATION
   ================================================================ */

QMainWindow {
    background-color: #0d0d14;
    color: #f0f0f5;
    font-family: "Inter", -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: transparent;
    font-family: "Inter", -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QLabel {
    color: #f0f0f5;
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
    background: rgba(255, 255, 255, 0.08);
    min-height: 32px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.15);
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
    background: rgba(255, 255, 255, 0.08);
    min-width: 32px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: rgba(255, 255, 255, 0.15);
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
    color: #f0f0f5;
    padding: 0;
    margin: 0;
    letter-spacing: -0.5px;
}

#appSubtitle {
    font-size: 12px;
    color: #6b6b80;
    padding: 0;
    margin: 0;
    letter-spacing: 0.3px;
}

#durationLabel {
    font-size: 44px;
    font-weight: 200;
    color: #f0f0f5;
    font-family: "JetBrains Mono", "SF Mono", "Cascadia Mono", "Consolas", monospace;
    letter-spacing: 2px;
}

#statusLabel {
    font-size: 12px;
    color: #6b6b80;
    letter-spacing: 0.2px;
}

#levelLabel {
    font-size: 10px;
    color: #4a4a5e;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
}

#savedLabel {
    font-size: 12px;
    color: #34d399;
    padding: 6px 0;
}

#deviceLabel {
    font-size: 12px;
    color: #a0a0b8;
    font-weight: 500;
}

/* ================================================================
   GROUP BOXES (Section containers)
   ================================================================ */

QGroupBox {
    background-color: #13131f;
    border: 1px solid #1e1e32;
    border-radius: 12px;
    margin-top: 16px;
    padding: 20px 16px 16px 16px;
    font-weight: 600;
    font-size: 13px;
    color: #a0a0b8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 14px;
    color: #6b6b80;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 700;
}

/* ================================================================
   INPUT FIELDS
   ================================================================ */

QLineEdit {
    background-color: #0f0f1a;
    border: 1px solid #2a2a42;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f0f0f5;
    font-size: 13px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

QLineEdit:focus {
    border-color: #6366f1;
    background-color: #111120;
}

QLineEdit:disabled {
    background-color: #0d0d14;
    color: #3a3a4e;
    border-color: #1a1a2a;
}

QLineEdit::placeholder {
    color: #4a4a5e;
}

/* ================================================================
   COMBO BOXES
   ================================================================ */

QComboBox {
    background-color: #0f0f1a;
    border: 1px solid #2a2a42;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f0f0f5;
    font-size: 13px;
    min-height: 18px;
}

QComboBox:hover {
    border-color: #3a3a58;
    background-color: #111120;
}

QComboBox:focus {
    border-color: #6366f1;
}

QComboBox:disabled {
    background-color: #0d0d14;
    color: #3a3a4e;
    border-color: #1a1a2a;
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
    border-top: 5px solid #6b6b80;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1a1a2a;
    border: 1px solid #2a2a42;
    border-radius: 8px;
    color: #f0f0f5;
    selection-background-color: #6366f1;
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
    background-color: #222238;
}

/* ================================================================
   CHECKBOXES
   ================================================================ */

QCheckBox {
    color: #a0a0b8;
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid #2a2a42;
    background-color: #0f0f1a;
}

QCheckBox::indicator:checked {
    background-color: #6366f1;
    border-color: #6366f1;
}

QCheckBox::indicator:hover {
    border-color: #6366f1;
}

QCheckBox:disabled {
    color: #3a3a4e;
}

QCheckBox::indicator:disabled {
    background-color: #0d0d14;
    border-color: #1a1a2a;
}

/* ================================================================
   BUTTONS — all buttons share the same base style
   (matching #sidebarNewBtn exactly)
   ================================================================ */

QPushButton {
    background-color: #1a1a2e;
    color: #8080a0;
    border: 1px solid #2a2a42;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.2px;
}

QPushButton:hover {
    background-color: #222238;
    color: #b0b0c4;
    border-color: #3a3a58;
}

QPushButton:pressed {
    background-color: #13131f;
    color: #8080a0;
    border-color: #2a2a42;
}

QPushButton:disabled {
    background-color: #111120;
    color: #3a3a4e;
    border: 1px solid #1a1a2a;
}

/* Record button — indigo fill, the one accent exception */
#recordBtn {
    background-color: #6366f1;
    color: #ffffff;
    border: none;
    min-width: 160px;
    border-radius: 10px;
}

#recordBtn:hover {
    background-color: #818cf8;
    color: #ffffff;
    border: none;
}

#recordBtn:pressed {
    background-color: #4f46e5;
    color: #ffffff;
    border: none;
}

/* Stop button — red fill */
#stopBtn {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
    min-width: 160px;
    border-radius: 10px;
}

#stopBtn:hover {
    background-color: #f87171;
    color: #ffffff;
    border: none;
}

#stopBtn:pressed {
    background-color: #dc2626;
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
    background-color: #1e1e32;
    border-left: 1px solid #1a1a2a;
    border-right: 1px solid #1a1a2a;
    width: 9px;
    margin: 12px 0;
    border-radius: 4px;
}

#contentSplitter::handle:hover {
    background-color: #2a2a42;
}

#contentSplitter::handle:pressed {
    background-color: #6366f1;
}

/* ================================================================
   SIDEBAR
   ================================================================ */

#sidebar {
    background-color: #0f0f1a;
    border-right: 1px solid #1e1e32;
}

#sidebarTitle {
    font-size: 11px;
    font-weight: 600;
    color: #505068;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

#sidebarSearch {
    background-color: #13131f;
    border: 1px solid #1e1e32;
    border-radius: 8px;
    padding: 7px 12px 7px 30px;
    color: #f0f0f5;
    font-size: 12px;
}

#sidebarSearch:focus {
    border-color: #6366f1;
    background-color: #161626;
}

#sidebarSearch::placeholder {
    color: #4a4a5e;
}

#sidebarNewBtn {
    padding: 8px 0;
    font-size: 12px;
    min-width: 0;
}

/* Meeting list item */
#sidebarItemName {
    font-size: 13px;
    color: #b0b0c4;
    font-weight: 500;
}

#sidebarItemMeta {
    font-size: 11px;
    color: #4a4a5e;
}

#sidebarItemPreview {
    font-size: 11px;
    color: #505068;
}

#sidebarDeleteBtn {
    background-color: transparent;
    color: #505068;
    border: none;
    font-size: 12px;
    font-weight: bold;
    padding: 0;
    min-width: 0;
    border-radius: 4px;
}

#sidebarDeleteBtn:hover {
    color: #f87171;
    background-color: rgba(248, 113, 113, 0.1);
}

#sidebarScroll {
    background-color: transparent;
    border: none;
}

/* Selected sidebar item uses dynamic property */
MeetingListItem[selected="true"] {
    background-color: #1a1a32;
    border-radius: 6px;
}

MeetingListItem[selected="true"] #sidebarItemName {
    color: #e0e0f0;
}

MeetingListItem:hover {
    background-color: #141424;
    border-radius: 6px;
}

/* ================================================================
   MEETING DETAIL BAR
   ================================================================ */

#meetingDetailBar {
    background-color: #13131f;
    border-bottom: 1px solid #1e1e32;
    padding: 6px 8px;
}

#meetingDetailTitle {
    font-size: 15px;
    font-weight: 600;
    color: #f0f0f5;
    letter-spacing: -0.2px;
}

#meetingDetailMeta {
    font-size: 11px;
    color: #6b6b80;
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
    background-color: #13131f;
    border: 1px solid #1e1e32;
    border-radius: 12px;
}

#transcriptHeader {
    font-size: 10px;
    font-weight: 700;
    color: #6b6b80;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    padding: 0;
}

#transcriptSegment {
    font-size: 13px;
    color: #c8c8d8;
    line-height: 1.6;
    padding: 6px 0;
}

#transcriptTimestamp {
    font-size: 10px;
    color: #4a4a5e;
    font-family: "JetBrains Mono", "SF Mono", "Cascadia Mono", "Consolas", monospace;
    font-weight: 500;
}

#transcriptSpeaker {
    font-size: 11px;
    color: #6366f1;
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
    background-color: #13131f;
    border: 1px solid #1e1e32;
    border-radius: 12px;
}

#summaryHeader {
    font-size: 10px;
    font-weight: 700;
    color: #6b6b80;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

#summaryText {
    font-size: 13px;
    color: #c8c8d8;
    line-height: 1.7;
    padding: 8px 0;
}

#summaryPlaceholder {
    font-size: 12px;
    color: #4a4a5e;
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
    background-color: #13131f;
    border-bottom: 1px solid #1e1e32;
    padding: 8px;
}

#retranscribeStatus {
    font-size: 12px;
    color: #a0a0b8;
}

#retranscribeProgress {
    background-color: #1a1a2a;
    border-radius: 3px;
}

#retranscribeProgress::chunk {
    background-color: #6366f1;
    border-radius: 3px;
}

/* ================================================================
   SPEAKER MAPPING PANEL
   ================================================================ */

#speakerPanel {
    background-color: #13131f;
    border-bottom: 1px solid #1e1e32;
    padding: 6px 12px;
}

#speakerPanelTitle {
    font-size: 10px;
    font-weight: 700;
    color: #6b6b80;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

#speakerLabel {
    font-size: 12px;
    color: #6b6b80;
    font-weight: 500;
}

#speakerInput {
    background-color: #0f0f1a;
    border: 1px solid #2a2a42;
    border-radius: 6px;
    padding: 5px 8px;
    color: #f0f0f5;
    font-size: 12px;
}

#speakerInput:focus {
    border-color: #6366f1;
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
    border: 1px solid #2a2a42;
    padding: 12px 14px;
    min-height: 36px;
}

#toast[toastType="success"] {
    background-color: rgba(52, 211, 153, 0.18);
    border-color: rgba(52, 211, 153, 0.35);
}

#toast[toastType="error"] {
    background-color: rgba(248, 113, 113, 0.18);
    border-color: rgba(248, 113, 113, 0.35);
}

#toast[toastType="warning"] {
    background-color: rgba(251, 191, 36, 0.18);
    border-color: rgba(251, 191, 36, 0.35);
}

#toast[toastType="info"] {
    background-color: rgba(96, 165, 250, 0.18);
    border-color: rgba(96, 165, 250, 0.35);
}

#toastIconSuccess {
    color: #34d399;
    font-size: 16px;
    font-weight: bold;
}

#toastIconError {
    color: #f87171;
    font-size: 16px;
    font-weight: bold;
}

#toastIconWarning {
    color: #fbbf24;
    font-size: 16px;
    font-weight: bold;
}

#toastIconInfo {
    color: #60a5fa;
    font-size: 16px;
    font-weight: bold;
}

#toastMessage {
    color: #f0f0f5;
    font-size: 13px;
    font-weight: 500;
}

#toastCloseBtn {
    background-color: transparent;
    color: #6b6b80;
    border: none;
    font-size: 13px;
    padding: 2px;
    min-width: 0;
    border-radius: 4px;
}

#toastCloseBtn:hover {
    color: #f0f0f5;
    background-color: rgba(255, 255, 255, 0.1);
}

/* ================================================================
   SETTINGS DIALOG
   ================================================================ */

QDialog {
    background-color: #0d0d14;
    color: #f0f0f5;
}

#settingsSection {
    font-size: 11px;
    font-weight: 700;
    color: #6366f1;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 4px 0;
}

#settingsDesc {
    font-size: 12px;
    color: #6b6b80;
    line-height: 1.5;
}

#settingsFieldLabel {
    font-size: 12px;
    color: #a0a0b8;
    font-weight: 500;
}

QDialogButtonBox QPushButton {
    min-width: 90px;
}

/* ================================================================
   MESSAGE BOXES
   ================================================================ */

QMessageBox {
    background-color: #13131f;
}

QMessageBox QLabel {
    color: #f0f0f5;
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
    background-color: #13131f;
    border: 1px solid #1e1e32;
    border-radius: 12px;
}

#recordingTitle {
    font-size: 10px;
    font-weight: 700;
    color: #6b6b80;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

#meetingNameInput {
    background-color: #0f0f1a;
    border: 1px solid #2a2a42;
    border-radius: 8px;
    padding: 10px 14px;
    color: #f0f0f5;
    font-size: 14px;
    font-weight: 500;
}

#meetingNameInput:focus {
    border-color: #6366f1;
    background-color: #111120;
}

/* ================================================================
   TAB BAR (for transcript/summary switching)
   ================================================================ */

#tabBar {
    background-color: transparent;
}

#tabActive {
    background-color: #1a1a2a;
    color: #f0f0f5;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
    min-width: 0;
}

#tabInactive {
    background-color: transparent;
    color: #6b6b80;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 500;
    min-width: 0;
}

#tabInactive:hover {
    color: #a0a0b8;
    background-color: rgba(255, 255, 255, 0.03);
}

/* ================================================================
   SECTION DIVIDER
   ================================================================ */

#divider {
    background-color: #1e1e32;
    max-height: 1px;
    min-height: 1px;
}
"""
