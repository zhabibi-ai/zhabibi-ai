"""Natiq Studio — visual theme and global Qt stylesheet."""

APP_NAME = "Natiq Studio"
APP_SUBTITLE = "استودیو بومی تطبیق و ویرایش صوت"
APP_TAGLINE = "دقت در واژه‌ها، وفاداری در معنا"
FONT_FAMILY = "Vazirmatn"


class C:
    # ==========================================
    # پالت اصلی برنامه
    # ==========================================
    bg = "#08110D"
    panel = "#0F1A16"          # رنگ پس‌زمینه اصلی پنل‌ها
    card = "#0F1A16"            # رنگ کارت‌ها
    card_alt = "#14221B"        # لایه روشن‌تر کارت
    input = "#0B1511"
    border = "#244235"
    border_soft = "#172C22"

    text = "#EEF7F1"
    muted = "#9AB0A3"
    subtle = "#657C70"

    # رنگ اصلی درخواستی کاربر
    accent = "#2E7032"
    accent2 = "#58B965"
    accent_deep = "#1E5525"
    accent_soft = "#18311D"

    # Accent طلایی؛ فقط برای وضعیت‌های مهم و نشانگر زمان
    gold = "#E6C97A"
    amber = "#E6A84D"
    red = "#EF5C63"
    green = "#69D48A"
    grey = "#A8B2AC"
    purple = "#B79BFF"
    white = "#F8FCF9"


# ==========================================
# استایل سراسری Qt
# ==========================================
_QSS = r"""
* {
    font-family: "@font", "Segoe UI", "Tahoma";
    font-size: 13px;
    color: @text;
    outline: none;
}

QWidget {
    background: transparent;
    selection-background-color: @accent_deep;
    selection-color: @white;
}

QLabel {
    background: transparent;
}

QToolTip {
    background: #17251E;
    color: @text;
    border: 1px solid @gold;
    padding: 8px 10px;
    border-radius: 7px;
}

#Root {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #0B1712, stop:0.45 #08110D, stop:1 #0A1510);
    border: 1px solid #20372B;
    border-radius: 16px;
}

#TitleBar {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #09120E, stop:0.55 #0C1712, stop:1 #09120E);
    border-bottom: 1px solid #244235;
}

#AppTitle {
    color: @white;
    font-size: 21px;
    font-weight: 700;
}

#AppSubtitle {
    color: @muted;
    font-size: 11px;
}

#Tagline {
    color: @gold;
    font-size: 12px;
    font-weight: 600;
}

#PipelineStatus {
    color: @green;
    font-size: 12.5px;
    font-weight: 700;
}

#LogoBox {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #3A8240, stop:0.55 #2E7032, stop:1 #25602A);
    border: 1px solid #4C9A52;
    border-radius: 13px;
}

#Badge {
    background: #0F1A16;
    border: 1px solid #2A493A;
    border-radius: 11px;
}

#BadgeDot {
    background: @green;
    border-radius: 4px;
}

#Card, #Panel {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 @card_alt, stop:1 @card);
    border: 1px solid @border;
    border-radius: 14px;
}

#Card:hover, #Panel:hover {
    border-color: #386448;
}

#CardTitle, #SectionLabel {
    color: @text;
    font-size: 14px;
    font-weight: 700;
}

#SectionLabelSubtle {
    color: @subtle;
    font-size: 11px;
}

#InfoDot {
    color: @gold;
    font-size: 12px;
    font-weight: 700;
}

#ModelNote {
    color: @muted;
    background: #122019;
    border: 1px solid #2B493A;
    border-radius: 8px;
    padding: 7px 8px;
    font-size: 10.5px;
}

#FileRow {
    background: @panel;
    border: 1px solid #264838;
    border-radius: 12px;
}

#FileRow:hover {
    background: #13241B;
    border-color: @accent;
}

#FileRow[loaded="true"] {
    background: #112219;
    border-color: #356846;
}

#FileIcon {
    background: #17321D;
    border: 1px solid #2E6B35;
    border-radius: 9px;
}

#FileName {
    color: @text;
    font-size: 12.5px;
    font-weight: 600;
}

#FileMeta {
    color: @muted;
    font-size: 11px;
}

#LtrLabel, #LtrMuted {
    direction: ltr;
}

#LtrLabel {
    color: @text;
}

#LtrMuted {
    color: @muted;
}

QComboBox {
    background: #0C1712;
    border: 1px solid #2A493A;
    border-radius: 9px;
    padding: 5px 28px 5px 10px;
    min-height: 29px;
}

QComboBox:hover,
QComboBox:focus {
    border-color: @accent;
    background: #122019;
}

QComboBox:disabled {
    color: #5B6B62;
    border-color: #1E3028;
}

QComboBox QAbstractItemView {
    background: #122019;
    border: 1px solid #3A5C48;
    selection-background-color: @accent_deep;
    selection-color: @white;
    padding: 5px;
}

QLineEdit {
    background: #0B1511;
    border: 1px solid #284638;
    border-radius: 9px;
    padding: 6px 10px;
    min-height: 28px;
}

QLineEdit:hover {
    border-color: #35664A;
}

QLineEdit:focus {
    border-color: @accent;
    background: #101E16;
}

QPushButton#Primary {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #33793A, stop:0.5 #2E7032, stop:1 #29652D);
    border: 1px solid #4C9A52;
    border-radius: 11px;
    color: #F7FFF8;
    font-size: 14px;
    font-weight: 700;
    min-height: 42px;
    padding: 0 15px;
}

QPushButton#Primary:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #38823E, stop:0.5 #327836, stop:1 #2E7032);
    border-color: #A1E0A5;
}

QPushButton#Primary:pressed {
    background: #24592A;
}

QPushButton#Primary:disabled {
    background: #18301D;
    border-color: #294B31;
    color: #647468;
}

QPushButton#Secondary,
QPushButton#Tab,
QPushButton#Seg {
    background: #0C1712;
    border: 1px solid #294638;
    border-radius: 9px;
    padding: 7px 12px;
    color: @muted;
    min-height: 29px;
}

QPushButton#Secondary:hover,
QPushButton#Tab:hover,
QPushButton#Seg:hover {
    background: #122019;
    border-color: #4E7E55;
    color: @text;
}

QPushButton#Tab:checked,
QPushButton#Seg:checked {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #2E7032, stop:1 #2E7032);
    border-color: #4C9A52;
    color: @white;
    font-weight: 700;
}

QPushButton#Tab:disabled,
QPushButton#Secondary:disabled {
    color: #586960;
    border-color: #1B2C23;
    background: #0A1310;
}

QPushButton#Danger {
    background: #281619;
    color: @red;
    border: 1px solid #7C3C42;
    border-radius: 10px;
    min-height: 32px;
    padding: 0 12px;
}

QPushButton#Danger:hover {
    background: #381C20;
    border-color: @red;
}

QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px;
}

QToolButton:hover {
    background: #13241B;
    border-color: #315A40;
}

QToolButton#NavBtn {
    background: #0C1712;
    border: 1px solid #203A2F;
    border-radius: 12px;
}

QToolButton#NavBtn:hover {
    background: #14241B;
    border-color: #416F48;
}

QToolButton#NavBtn:checked {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #2E7032, stop:1 #2E7032);
    border-color: #4C9A52;
}

QToolButton#CloseBtn:hover {
    background: #6A252A;
    border-color: #A6474E;
}

QToolButton#PlayBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #35803B, stop:0.55 #2E7032, stop:1 #25602A);
    border: 2px solid #4C9A52;
    border-radius: 31px;
}

QToolButton#PlayBtn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #3C8A42, stop:0.55 #33793A, stop:1 #2E7032);
}

QToolButton#TransportBtn {
    background: #0D1813;
    border: 1px solid #29483A;
    border-radius: 20px;
    color: @text;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    font-weight: 700;
}

QToolButton#TransportBtn:hover {
    background: #17251D;
    border-color: #577C57;
    color: @gold;
}

QSlider::groove:horizontal {
    height: 5px;
    background: #273D31;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #2E7032, stop:1 #3F8A45);
    border-radius: 3px;
}

QSlider::add-page:horizontal {
    background: #273D31;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #D5E9D7;
    border: 2px solid #4B9250;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: @gold;
    border-color: #F4DA8E;
}

QProgressBar {
    background: #1C2A22;
    border: 1px solid #2A4336;
    border-radius: 4px;
    max-height: 6px;
    min-height: 6px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #2E7032, stop:1 #3F8A45);
    border-radius: 4px;
}

QScrollArea {
    background: @panel;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: @panel;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 0 4px 2px;
}

QScrollBar::handle:vertical {
    background: #315340;
    border-radius: 4px;
    min-height: 34px;
}

QScrollBar::handle:vertical:hover {
    background: #4D7551;
}

QScrollBar::add-line,
QScrollBar::sub-line {
    height: 0;
    width: 0;
}

QScrollBar::add-page,
QScrollBar::sub-page {
    background: transparent;
}

QPlainTextEdit,
QTextEdit {
    background: #0D1914;
    border: none;
    color: @text;
    selection-background-color: #2B5731;
    font-size: 15px;
    padding: 10px;
}

#SearchBar {
    background: #0B1511;
    border: 1px solid #294638;
}

#SearchBar:focus {
    border-color: @accent;
}

#EditorBody {
    background: #0C1812;
    border: 1px solid #1F392E;
    border-radius: 10px;
}

QTabWidget::pane {
    background: @panel;
    border: 1px solid #20392D;
    border-radius: 10px;
    top: -1px;
}

QTabBar {
    qproperty-drawBase: 0;
}

QTabBar::tab {
    background: #0B1712;
    color: @muted;
    border: 1px solid #213B2F;
    padding: 8px 12px;
    border-radius: 8px;
    margin: 0 3px 3px 0;
}

QTabBar::tab:selected {
    background: #17301D;
    color: @white;
    border-color: #5C955E;
}

QTabBar::tab:hover:!selected {
    background: #132219;
    border-color: #3B5B42;
}

QListWidget {
    background: #0B1712;
    border: 1px solid #1D352A;
    border-radius: 10px;
    outline: none;
}

QListWidget::item {
    background: transparent;
    border: none;
    padding: 0;
}

#EditorFooter {
    background: #0F1A16;
    border-top: 1px solid #254335;
}

#EmptyStateTitle {
    color: @text;
    font-size: 14px;
    font-weight: 700;
}

#EmptyStateText {
    color: @muted;
    font-size: 12px;
}

#InspectorCount {
    color: @gold;
    font-size: 11px;
    font-weight: 600;
}

#InspectorCard {
    background: #0E1914;
    border: 1px solid #284538;
    border-radius: 11px;
}

#SegItem {
    background: #0D1914;
    border: 1px solid #254337;
    border-radius: 10px;
}

#SegItem:hover,
#SegItem[selected="true"] {
    background: #132219;
    border-color: #47724B;
}

#SegNum {
    background: #16251C;
    border: 1px solid #294638;
    border-radius: 11px;
    color: @muted;
}

#SegTime {
    color: @muted;
}

#SegText {
    color: #CBD8D0;
}

#LogBox {
    background: #0B1712;
    border: 1px solid #294638;
    border-radius: 10px;
    padding: 8px;
}

#Muted {
    color: @muted;
}

#Hint {
    color: @amber;
    font-size: 11px;
}

#PageTitle {
    color: @white;
    font-size: 16px;
    font-weight: 700;
}

QDialog {
    background: @bg;
}

QDialog#PasteDialog {
    border: 1px solid @border;
    border-radius: 12px;
}

QMenu {
    background: #122019;
    border: 1px solid #3A5C48;
    border-radius: 9px;
    padding: 6px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 6px;
    color: @text;
}

QMenu::item:selected {
    background: @accent_deep;
    color: @white;
}

QMenu::item:disabled {
    color: #586960;
}

QMenu::separator {
    height: 1px;
    background: #244235;
    margin: 5px 8px;
}

QTableWidget {
    background: #0B1712;
    border: 1px solid #1D352A;
    border-radius: 10px;
    gridline-color: #16281F;
    selection-background-color: @accent_deep;
}

QTableWidget::item {
    padding: 5px 8px;
    border: none;
}

QHeaderView {
    background: transparent;
}

QHeaderView::section {
    background: #10201A;
    color: @muted;
    border: none;
    border-bottom: 1px solid #244235;
    padding: 6px 8px;
    font-weight: 700;
}

QTableCornerButton::section {
    background: #10201A;
    border: none;
}

#MetricCard {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #14221B, stop:1 #0E1A15);
    border: 1px solid #244235;
    border-radius: 13px;
}

#MetricTitle {
    color: @muted;
    font-size: 11.5px;
    font-weight: 600;
}

#MetricValue {
    color: @white;
    font-size: 25px;
    font-weight: 700;
}

#MetricSub {
    color: @subtle;
    font-size: 11px;
}

#StatNum {
    color: @white;
    font-size: 17px;
    font-weight: 700;
}
"""


def build_qss() -> str:
    tokens = {
        "@font": FONT_FAMILY,
        "@bg": C.bg,
        "@panel": C.panel,
        "@card": C.card,
        "@card_alt": C.card_alt,
        "@input": C.input,
        "@border": C.border,
        "@border_soft": C.border_soft,
        "@text": C.text,
        "@muted": C.muted,
        "@subtle": C.subtle,
        "@accent": C.accent,
        "@accent2": C.accent2,
        "@accent_deep": C.accent_deep,
        "@gold": C.gold,
        "@amber": C.amber,
        "@green": C.green,
        "@red": C.red,
        "@grey": C.grey,
        "@purple": C.purple,
        "@white": C.white,
    }
    qss = _QSS
    for key in sorted(tokens, key=len, reverse=True):
        qss = qss.replace(key, tokens[key])
    return qss
