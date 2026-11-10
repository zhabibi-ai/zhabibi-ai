"""Main UI for Natiq Studio.

The class intentionally exposes signals/methods used by the existing processing
layer. Heavy processing, ASR and media playback remain outside this UI module.
"""

from __future__ import annotations

import difflib
import json
from time import strftime

from PySide6.QtCore import QEvent, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizeGrip,
    QApplication,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QSizePolicy,
)

from core.issue_format import PROMPT
from .icons import icon, pixmap
from .highlight_dialog import HighlightDialog
from .issues_panel import IssuesPanel
from .log_page import LogPage, guess_level
from .monitor_page import MonitorPage
from .styles import APP_NAME, APP_SUBTITLE, APP_TAGLINE, C
from .widgets import (
    DEFAULT_HIGHLIGHTS,
    Card,
    ClickSlider,
    Combo,
    FileRow,
    InfoDot,
    LtrLabel,
    RtlLabel,
    SectionLabel,
    TextEditor,
    Toggle,
    WaveformWidget,
)


# ==========================================
# تبدیل و قالب‌بندی ساده متن
# ==========================================
FA = str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹،")


def fa(value) -> str:
    return str(value).translate(FA)


def ms_text(ms: int) -> str:
    total = max(0, int(ms)) // 1000
    if total >= 3600:
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"
    return f"{total // 60:02d}:{total % 60:02d}"


# ==========================================
# کارت بررسی خطا
# ==========================================
class PasteDialog(QDialog):
    def __init__(self, title, hint, parent=None):
        super().__init__(parent)
        self.setObjectName("PasteDialog")
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(640, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        head = QLabel(title)
        head.setObjectName("PageTitle")
        layout.addWidget(head)
        note = QLabel(hint)
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("متن را اینجا بچسبانید (Ctrl+V)...")
        self.edit.setStyleSheet("QPlainTextEdit{border:1px solid #294638; border-radius:10px;}")
        layout.addWidget(self.edit, 1)

        row = QHBoxLayout()
        ok = QPushButton("تأیید و افزودن")
        ok.setObjectName("Primary")
        cancel = QPushButton("انصراف")
        cancel.setObjectName("Secondary")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row.addWidget(ok, 1)
        row.addWidget(cancel)
        layout.addLayout(row)
        self.edit.setFocus()

    def text(self):
        return self.edit.toPlainText()


# ==========================================
# نوار عنوان و وضعیت
# ==========================================
class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(74)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(12)

        logo = QLabel()
        logo.setObjectName("LogoBox")
        logo.setFixedSize(50, 50)
        logo.setAlignment(Qt.AlignCenter)
        logo.setPixmap(pixmap("wave", "#E8FFF2", 28))
        layout.addWidget(logo)

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)

        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")

        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("AppSubtitle")

        title_layout.addStretch()
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        separator = QFrame()
        separator.setFixedSize(1, 34)
        separator.setStyleSheet(f"background:{C.border};")
        layout.addSpacing(8)
        layout.addWidget(separator)
        layout.addSpacing(4)

        tagline = QLabel(APP_TAGLINE)
        tagline.setObjectName("Tagline")
        layout.addWidget(tagline)

        separator2 = QFrame()
        separator2.setFixedSize(1, 34)
        separator2.setStyleSheet(f"background:{C.border};")
        layout.addSpacing(10)
        layout.addWidget(separator2)
        layout.addSpacing(4)

        self.lbl_pipeline_status = QLabel("● آماده")
        self.lbl_pipeline_status.setObjectName("PipelineStatus")
        layout.addWidget(self.lbl_pipeline_status)
        layout.addStretch()

        badge = QFrame()
        badge.setObjectName("Badge")
        badge_layout = QHBoxLayout(badge)
        badge_layout.setContentsMargins(12, 6, 12, 6)
        badge_layout.setSpacing(8)

        self.dot = QLabel()
        self.dot.setObjectName("BadgeDot")
        self.dot.setFixedSize(8, 8)

        self.gpu = QLabel("GPU: — | RAM: —")
        self.gpu.setStyleSheet(
            f"color:{C.green}; font-weight:700;"
        )

        separator3 = QFrame()
        separator3.setFixedSize(1, 22)
        separator3.setStyleSheet(f"background:{C.border};")

        model_label = QLabel("مدل:")
        model_label.setObjectName("Muted")

        self.model = LtrLabel("base", muted=True)

        for widget in (
            self.dot,
            self.gpu,
            separator3,
            model_label,
            self.model,
        ):
            badge_layout.addWidget(widget)

        layout.addWidget(badge)

        self.btn_min = self._window_button("min", "کوچک‌سازی")
        self.btn_max = self._window_button("max", "بزرگ‌نمایی / بازگشت")
        self.btn_close = self._window_button("close", "بستن برنامه")
        self.btn_close.setObjectName("CloseBtn")

        for button in (self.btn_min, self.btn_max, self.btn_close):
            layout.addWidget(button)

        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(window.toggle_maximize)
        self.btn_close.clicked.connect(window.close)

    def _window_button(self, name, tooltip):
        button = QToolButton()
        button.setFixedSize(34, 32)
        button.setIcon(icon(name, "#CFE3D6", 16, "#FFFFFF"))
        button.setIconSize(QSize(16, 16))
        button.setToolTip(tooltip)
        return button

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.LeftButton
            and self.window.windowHandle()
        ):
            self.window.windowHandle().startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window.toggle_maximize()


# ==========================================
# پنجره اصلی
# ==========================================
class MainWindow(QWidget):
    # ==========================================
    # سیگنال‌های ورودی فایل
    # ==========================================
    media_open_requested = Signal()
    asr_open_requested = Signal()
    issues_open_requested = Signal()
    corrected_open_requested = Signal()

    # ==========================================
    # سیگنال‌های Pipeline
    # ==========================================
    process_requested = Signal(dict)
    cancel_requested = Signal()

    # ==========================================
    # سیگنال‌های پخش و کنترل صوت
    # ==========================================
    play_toggled = Signal(bool)
    seek_requested = Signal(float)
    skip_requested = Signal(int)
    volume_changed = Signal(int)
    speed_changed = Signal(float)
    word_clicked = Signal(int, int)

    # ==========================================
    # سیگنال‌های ناوبری و View
    # ==========================================
    nav_changed = Signal(str)

    # ==========================================
    # سیگنال‌های همگام‌سازی صدا و متن
    # ==========================================
    follow_toggled = Signal(bool)
    locate_requested = Signal()
    issues_paste_requested = Signal(str)
    apply_requested = Signal()
    reset_requested = Signal()
    edit_start_requested = Signal()
    edit_save_requested = Signal()
    edit_cancel_requested = Signal()

    def __init__(self):
        super().__init__()
        self._running = False
        self._sync_available = False
        self._dirty = False
        self._editing = False

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.LeftToRight)

        self.resize(1480, 860)
        self.setMinimumSize(1100, 680)
        self._playing = False

        # ==========================================
        # ریشه و ساختار کلی
        # ==========================================
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.root = QFrame()
        self.root.setObjectName("Root")
        outer.addWidget(self.root)

        root_layout = QVBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.titlebar = TitleBar(self)
        root_layout.addWidget(self.titlebar)

        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(10)

        body.addWidget(self._build_nav())

        # سه ستون ثابت: کناره‌ها عرض مشخص دارند و فقط ستون وسط کش می‌آید.
        # (قبلاً Splitter بود و با ماوس جابه‌جا می‌شد؛ حالا هیچ دستگیره‌ای وجود ندارد.)
        self.left_panel = self._build_left()
        self.center_panel = self._build_center()
        self.right_panel = self._build_right()
        self.center_panel.setMinimumWidth(420)
        self._apply_column_widths(self.width())

        body.addWidget(self.left_panel, 0)
        body.addWidget(self.center_panel, 1)
        body.addWidget(self.right_panel, 0)
        root_layout.addLayout(body, 1)

        self.grip = QSizeGrip(self.root)
        self.grip.setFixedSize(16, 16)

        self.cb_model.currentTextChanged.connect(
            lambda value: self.titlebar.model.setText(value)
        )

        self._refresh_action_state()
        QApplication.instance().installEventFilter(self)

    # ==========================================
    # Space = پخش / توقف
    # ==========================================
    @staticmethod
    def _user_is_typing() -> bool:
        if QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None:
            return True
        w = QApplication.focusWidget()
        if isinstance(w, QLineEdit):
            return True
        if isinstance(w, (QTextEdit, QPlainTextEdit)) and not w.isReadOnly():
            return True
        return isinstance(w, QComboBox) and w.isEditable()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and self.isActiveWindow() and not event.isAutoRepeat():
            mods, key = event.modifiers(), event.key()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            alt = bool(mods & Qt.KeyboardModifier.AltModifier)
            if key == Qt.Key_Space and not (mods & ~Qt.KeyboardModifier.ControlModifier):
                # Space ساده فقط وقتی تایپ نمی‌کنی؛ Ctrl+Space همیشه
                if ctrl or not self._user_is_typing():
                    self.play_toggled.emit(not self._playing)
                    return True
            elif alt and not ctrl and key in (Qt.Key_Left, Qt.Key_Right):
                self.skip_requested.emit(-5000 if key == Qt.Key_Left else 5000)
                return True
        return super().eventFilter(obj, event)

    # ==========================================
    # مدیریت پنجره
    # ==========================================
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _on_nav_page(self, key):
        index = {"editor": 0, "monitor": 1, "log": 2}.get(key, 0)
        self.main_stack.setCurrentIndex(index)
        self.player_card.setVisible(index == 0)

    def _apply_column_widths(self, total_width: int):
        """عرض ستون‌های کناری متناسب با پنجره، ولی همیشه بین یک حداقل و حداکثر ثابت."""
        left = max(285, min(340, int(total_width * 0.205)))
        right = max(300, min(370, int(total_width * 0.215)))
        self.left_panel.setFixedWidth(left)
        self.right_panel.setFixedWidth(right)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_column_widths(self.width())
        self.grip.move(
            self.root.width() - 18,
            self.root.height() - 18,
        )

    # ==========================================
    # نوار ناوبری
    # ==========================================
    def _build_nav(self):
        nav = QWidget()
        nav.setFixedWidth(48)

        layout = QVBoxLayout(nav)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.nav_group = QButtonGroup(self)

        buttons = [
            ("editor", "home", "فضای کاری ویرایش"),
            ("monitor", "activity", "مانیتورینگ سخت‌افزار"),
            ("log", "list", "لاگ عملیات"),
        ]

        for key, icon_name, tooltip in buttons:
            button = QToolButton()
            button.setObjectName("NavBtn")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setFixedSize(46, 46)
            button.setIcon(icon(icon_name, C.gold, 21, "#FFFFFF"))
            button.setIconSize(QSize(21, 21))
            button.setChecked(key == "editor")
            button.setToolTip(tooltip)
            button.clicked.connect(
                lambda _=False, value=key: self.nav_changed.emit(value)
            )

            self.nav_group.addButton(button)
            layout.addWidget(button)

        layout.addStretch()
        return nav

    # ==========================================
    # ستون ورودی پروژه و تنظیمات
    # ==========================================
    def _build_left(self):
        panel = QWidget()
        panel.setObjectName("Panel")
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setObjectName("Panel")
        column = QVBoxLayout(scroll_content)
        column.setContentsMargins(0, 0, 8, 0)
        column.setSpacing(9)

        self.media_row = FileRow(
            "music",
            "انتخاب فایل صوتی / تصویری",
        )
        self.media_row.clicked.connect(self.media_open_requested)
        self.media_row.removed.connect(self.media_row.clear)
        self.media_row.removed.connect(self._refresh_action_state)
        column.addWidget(
            SectionLabel(
                "رسانه",
                "music",
                C.accent2,
                "مرجع زمان‌بندی و پخش",
            )
        )
        column.addWidget(self.media_row)

        self.asr_row = FileRow(
            "doc",
            "انتخاب متن خام",
        )
        self.asr_row.clicked.connect(self.asr_open_requested)
        self.asr_row.removed.connect(self.asr_row.clear)
        self.asr_row.removed.connect(self._refresh_action_state)
        column.addWidget(
            SectionLabel(
                "متن خام",
                "doc",
                C.accent2,
                "یکی از دو متن (خام یا اصلاح‌شده) لازم است",
            )
        )
        column.addWidget(self.asr_row)

        self.issues_row = FileRow(
            "list",
            "انتخاب فایل لیست ایرادات",
        )
        self.issues_row.clicked.connect(self.issues_open_requested)
        self.issues_row.removed.connect(self.issues_row.clear)
        self.issues_row.removed.connect(self._refresh_action_state)
        column.addWidget(
            SectionLabel(
                "لیست ایرادات",
                "list",
                C.amber,
                "اختیاری — فایل یا کپی‌پیست",
            )
        )
        column.addWidget(self.issues_row)

        issues_buttons = QHBoxLayout()
        issues_buttons.setSpacing(6)
        self.btn_paste_issues = QPushButton("چسباندن لیست")
        self.btn_paste_issues.setObjectName("Secondary")
        self.btn_paste_issues.setIcon(icon("paste", C.muted, 15, C.text))
        self.btn_paste_issues.setToolTip("لیست ایرادات را مستقیم کپی‌پیست کنید (بدون نیاز به فایل)")
        self.btn_paste_issues.clicked.connect(self.open_issues_paste_dialog)
        self.btn_copy_template = QPushButton("قالب Gemini")
        self.btn_copy_template.setObjectName("Secondary")
        self.btn_copy_template.setIcon(icon("sparkle", C.muted, 15, C.text))
        self.btn_copy_template.setToolTip("پرامپت و قالب ایرادات را کپی می‌کند تا به Gemini بدهید")
        self.btn_copy_template.clicked.connect(self.copy_issue_template)
        issues_buttons.addWidget(self.btn_paste_issues, 1)
        issues_buttons.addWidget(self.btn_copy_template, 1)
        column.addLayout(issues_buttons)

        self.corrected_row = FileRow(
            "edit",
            "افزودن متن اصلاح‌شده",
        )
        self.corrected_row.clicked.connect(self.corrected_open_requested)
        self.corrected_row.removed.connect(self.corrected_row.clear)
        self.corrected_row.removed.connect(self._refresh_action_state)
        column.addWidget(
            SectionLabel(
                "متن اصلاح‌شده",
                "sparkle",
                C.purple,
                "اگر باشد، همین متن با صوت همگام می‌شود",
            )
        )
        column.addWidget(self.corrected_row)

        # ==========================================
        # تنظیمات Faster-Whisper
        # ==========================================
        settings_card = Card("تنظیمات پردازش", "gear")
        settings_card.body.setSpacing(8)

        self.cb_model = Combo()
        self.cb_model.addItems(["base", "tiny", "small", "medium", "large-v3"])
        self.cb_model.setCurrentText("base")

        self.cb_lang = Combo()
        self.cb_lang.addItems(["fa", "en", "auto"])
        self.cb_lang.setCurrentText("fa")

        self.cb_device = Combo()
        self.cb_device.addItems(["auto", "cuda", "cpu"])
        self.cb_device.setCurrentText("auto")

        self.cb_compute = Combo()
        self.cb_compute.addItems(["auto", "float16", "int8", "int8_float16"])
        self.cb_compute.setCurrentText("auto")

        for combo in (
            self.cb_model,
            self.cb_lang,
            self.cb_device,
            self.cb_compute,
        ):
            combo.setMinimumWidth(92)
            combo.setMaximumWidth(140)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            combo.setLayoutDirection(Qt.LeftToRight)

        self.tg_vad = Toggle(True)
        self.tg_cond = Toggle(False)
        self.tg_word = Toggle(True)
        self.tg_word.setEnabled(False)

        model_help = (
            "مدل Whisper برای تبدیل گفتار به متن.\n\n"
            "tiny / base: سبک و سریع\n"
            "small / medium: دقیق‌تر و سنگین‌تر\n"
            "large-v3: سنگین‌ترین گزینه و مناسب سیستم‌های قوی."
        )
        lang_help = (
            "زبان گفتار را مشخص می‌کند. برای پروژه فارسی، "
            "گزینه fa پیشنهاد می‌شود."
        )
        device_help = (
            "محل اجرای مدل است.\n\n"
            "auto = اول GPU (CUDA)، و اگر نبود یا خطا داد، خودکار CPU\n"
            "cuda = فقط GPU NVIDIA (در صورت نبود، CPU)\n"
            "cpu = اجرای پردازش روی پردازنده."
        )
        compute_help = (
            "نوع محاسبات مدل را مشخص می‌کند.\n\n"
            "auto = بهترین گزینه برای دستگاه انتخابی (GPU: float16، CPU: int8).\n"
            "float16 برای CUDA مناسب است.\n"
            "int8 برای CPU یا VRAM محدود مفید است."
        )
        vad_help = (
            "بخش‌های سکوت یا بدون گفتار را بهتر شناسایی می‌کند "
            "و معمولاً زمان پردازش را کاهش می‌دهد."
        )
        cond_help = (
            "متن بخش قبل را به‌عنوان context در نظر می‌گیرد. "
            "گاهی پیوستگی را بهتر می‌کند، اما می‌تواند خطاهای قبلی "
            "را نیز به بخش بعد منتقل کند."
        )
        word_help = (
            "برای هر کلمه timestamp استخراج می‌کند. این قابلیت "
            "برای همگام‌سازی دقیق متن با صوت و Ctrl+Click ضروری است. با Alt+Click می‌توانید لنگر دستی بسازید."
        )

        def add_setting_row(
            label_text,
            widget,
            tooltip,
            disabled=False,
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)

            label = QLabel(label_text)
            label.setToolTip(tooltip)

            info = InfoDot(tooltip)

            row.addWidget(label)
            row.addWidget(info)
            if isinstance(widget, Combo):
                row.addSpacing(4)
                row.addWidget(widget, 1)
            else:
                row.addStretch()
                row.addWidget(widget)

            if disabled:
                widget.setEnabled(False)

            settings_card.body.addLayout(row)

        add_setting_row("مدل تشخیص", self.cb_model, model_help)
        add_setting_row("زبان", self.cb_lang, lang_help)
        add_setting_row("دستگاه", self.cb_device, device_help)
        add_setting_row("نوع محاسبه", self.cb_compute, compute_help)
        add_setting_row("حذف سکوت (VAD)", self.tg_vad, vad_help)
        add_setting_row("متن قبلی (Context)", self.tg_cond, cond_help)
        add_setting_row(
            "Timestamp کلمات",
            self.tg_word,
            word_help,
            disabled=True,
        )

        note = QLabel(
            "ⓘ  برای کار اصلی Natiq، Timestamp کلمات همیشه فعال است."
        )
        note.setObjectName("ModelNote")
        note.setWordWrap(True)
        settings_card.body.addWidget(note)

        column.addWidget(settings_card)
        column.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        # ==========================================
        # نوار عملیات
        # ==========================================
        bottom = QVBoxLayout()
        progress_row = QHBoxLayout()

        self.proc_time = QLabel("00:00")
        self.proc_time.setObjectName("Muted")

        self.proc_bar = QProgressBar()
        self.proc_bar.setRange(0, 100)
        self.proc_bar.setTextVisible(False)

        progress_row.addWidget(self.proc_time)
        progress_row.addWidget(self.proc_bar, 1)
        bottom.addLayout(progress_row)

        self.btn_process = QPushButton("✦  تحلیل صوت و متن")
        self.btn_process.setObjectName("Primary")
        self.btn_process.setToolTip(
            "اجرای کامل Pipeline: تبدیل گفتار، زمان‌بندی و تطبیق متن خام."
        )
        self.btn_process.clicked.connect(
            lambda: self.process_requested.emit(self.settings())
        )
        bottom.addWidget(self.btn_process)

        self.btn_apply = QPushButton("↻  اعمال متن و ایرادات جدید")
        self.btn_apply.setObjectName("Secondary")
        self.btn_apply.setToolTip(
            "بعد از تحلیل، اگر متن یا لیست ایرادات را عوض کردید، با این دکمه (بدون تحلیل مجدد صوت) اعمال می‌شود."
        )
        self.btn_apply.setEnabled(False)
        self.btn_apply.setVisible(False)
        self.btn_apply.clicked.connect(lambda *_: self.apply_requested.emit())
        bottom.addWidget(self.btn_apply)

        self.btn_reset = QPushButton("⟲  ریست — شروع فایل جدید")
        self.btn_reset.setObjectName("Danger")
        self.btn_reset.setToolTip("همه‌ی فایل‌ها، متن‌ها و نتایج پاک می‌شود تا فایل بعدی را بدهید (تنظیمات مدل حفظ می‌شود).")
        self.btn_reset.setEnabled(False)
        self.btn_reset.clicked.connect(lambda *_: self.reset_requested.emit())
        bottom.addWidget(self.btn_reset)

        self.btn_cancel = QPushButton("■  توقف عملیات")
        self.btn_cancel.setObjectName("Danger")
        self.btn_cancel.setToolTip("پردازش جاری را متوقف می‌کند.")
        self.btn_cancel.hide()
        self.btn_cancel.clicked.connect(lambda *_: self.cancel_requested.emit())
        bottom.addWidget(self.btn_cancel)

        self.lbl_hint = QLabel("")
        self.lbl_hint.setObjectName("Hint")
        self.lbl_hint.setWordWrap(True)
        bottom.addWidget(self.lbl_hint)

        main_layout.addLayout(bottom)
        return panel

    # ==========================================
    # پلیر صوت و ویرایشگر
    # ==========================================
    def _build_center(self):
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)

        # ==========================================
        # پلیر حرفه‌ای صوت
        # ==========================================
        player = Card()
        player.setObjectName("AudioCard")
        self.player_card = player

        player_row = QHBoxLayout()
        player_row.setSpacing(12)

        # دکمه پخش در بالا و عقب/جلو دقیقاً زیر آن
        transport = QVBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(8)

        self.btn_play = QToolButton()
        self.btn_play.setObjectName("PlayBtn")
        self.btn_play.setFixedSize(62, 62)
        self.btn_play.setIcon(icon("play", "#FFFFFF", 27))
        self.btn_play.setIconSize(QSize(27, 27))
        self.btn_play.setToolTip("پخش / توقف  (Space)")
        self.btn_play.clicked.connect(
            lambda: self.play_toggled.emit(not self._playing)
        )
        transport.addWidget(self.btn_play, 0, Qt.AlignCenter)

        skip_row = QHBoxLayout()
        skip_row.setSpacing(6)

        self.btn_skip_back = QToolButton()
        self.btn_skip_back.setObjectName("TransportBtn")
        self.btn_skip_back.setText("−5")
        self.btn_skip_back.setLayoutDirection(Qt.LeftToRight)
        self.btn_skip_back.setFixedSize(40, 40)
        self.btn_skip_back.setToolTip("۵ ثانیه به عقب")
        self.btn_skip_back.clicked.connect(
            lambda: self.skip_requested.emit(-5000)
        )

        self.btn_skip_fw = QToolButton()
        self.btn_skip_fw.setObjectName("TransportBtn")
        self.btn_skip_fw.setText("+5")
        self.btn_skip_fw.setLayoutDirection(Qt.LeftToRight)
        self.btn_skip_fw.setFixedSize(40, 40)
        self.btn_skip_fw.setToolTip("۵ ثانیه به جلو")
        self.btn_skip_fw.clicked.connect(
            lambda: self.skip_requested.emit(5000)
        )

        skip_row.addWidget(self.btn_skip_back)
        skip_row.addWidget(self.btn_skip_fw)
        transport.addLayout(skip_row)
        player_row.addLayout(transport)

        audio_column = QVBoxLayout()
        audio_column.setContentsMargins(0, 0, 0, 0)
        audio_column.setSpacing(8)

        # نوار باریک طلایی برای تشخیص سطح حرفه‌ای پلیر
        accent_line = QFrame()
        accent_line.setFixedHeight(2)
        accent_line.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 rgba(230,201,122,0), stop:0.18 {C.gold}, "
            f"stop:0.82 {C.gold}, stop:1 rgba(230,201,122,0));"
        )
        audio_column.addWidget(accent_line)

        self.wave = WaveformWidget()
        self.wave.setToolTip("برای پرش مستقیم روی موج صوتی کلیک کنید.")
        self.wave.seek_requested.connect(self.seek_requested.emit)
        audio_column.addWidget(self.wave)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.time_lbl = LtrLabel("00:00  /  00:00", muted=True)
        self.time_lbl.setMinimumWidth(108)
        controls.addWidget(self.time_lbl)
        controls.addStretch(1)

        volume_label = QLabel("صدا")
        volume_label.setObjectName("Muted")

        self.volume = ClickSlider()
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume.setMinimumWidth(90)
        self.volume.setMaximumWidth(300)
        self.volume.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.volume.setToolTip("بلندی صدای پخش")
        self.volume.valueChanged.connect(self.volume_changed.emit)

        speed_label = QLabel("سرعت")
        speed_label.setObjectName("Muted")

        self.cb_speed = Combo()
        self.cb_speed.addItems(["0.5×", "0.75×", "1.0×", "1.25×", "1.5×", "2.0×"])
        self.cb_speed.setCurrentText("1.0×")
        self.cb_speed.setFixedWidth(78)
        self.cb_speed.setLayoutDirection(Qt.LeftToRight)
        self.cb_speed.setToolTip("سرعت پخش صوت")
        self.cb_speed.currentTextChanged.connect(
            lambda value: self.speed_changed.emit(float(value[:-1]))
        )

        controls.addWidget(volume_label)
        controls.addWidget(self.volume, 1)

        self.lbl_volume = LtrLabel("100%", muted=True)
        self.lbl_volume.setMinimumWidth(38)
        self.volume.valueChanged.connect(lambda v: self.lbl_volume.setText(f"{v}%"))
        controls.addWidget(self.lbl_volume)
        controls.addSpacing(8)
        controls.addWidget(speed_label)
        controls.addWidget(self.cb_speed)
        audio_column.addLayout(controls)

        player_row.addLayout(audio_column, 1)
        player.body.addLayout(player_row)
        column.addWidget(player)

        # ==========================================
        # کارت متن، تب‌ها و جستجوی متن
        # ==========================================
        self.main_stack = QStackedWidget()

        editor_page = QWidget()
        editor_layout = QVBoxLayout(editor_page)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        editor_card = QFrame()
        editor_card.setObjectName("Card")
        editor_card_layout = QVBoxLayout(editor_card)
        editor_card_layout.setContentsMargins(7, 7, 7, 0)
        editor_card_layout.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setSpacing(7)
        search_row.setDirection(QBoxLayout.RightToLeft)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("SearchBar")
        self.search_edit.setPlaceholderText("جستجو در متن...")
        self.search_edit.setLayoutDirection(Qt.RightToLeft)
        self.search_edit.setAlignment(Qt.AlignRight)
        self.search_edit.setToolTip("جستجوی عبارت در متن فعال")
        self.search_edit.textChanged.connect(self._apply_search)
        search_row.addWidget(self.search_edit, 1)

        self.btn_search_prev = QPushButton("قبلی")
        self.btn_search_prev.setObjectName("Secondary")
        self.btn_search_prev.setFixedWidth(58)
        self.btn_search_prev.setToolTip("نتیجه قبلی")
        self.btn_search_prev.clicked.connect(lambda: self._search_step(backward=True))
        search_row.addWidget(self.btn_search_prev)

        self.btn_search_next = QPushButton("بعدی")
        self.btn_search_next.setObjectName("Secondary")
        self.btn_search_next.setFixedWidth(58)
        self.btn_search_next.setToolTip("نتیجه بعدی")
        self.btn_search_next.clicked.connect(lambda: self._search_step(backward=False))
        search_row.addWidget(self.btn_search_next)

        self.btn_follow = QPushButton("دنبال‌کردن")
        self.btn_follow.setObjectName("Seg")
        self.btn_follow.setCheckable(True)
        self.btn_follow.setChecked(False)
        self.btn_follow.setCursor(Qt.PointingHandCursor)
        self.btn_follow.setToolTip(
            "اگر روشن باشد متن همراه پخش صدا حرکت می‌کند.\n"
            "پیش‌فرض خاموش است تا متن بی‌دلیل بالا و پایین نپرد؛ "
            "برای شنیدن هر کلمه از Ctrl+Click استفاده کنید."
        )
        self.btn_follow.toggled.connect(self.follow_toggled.emit)
        

        self.btn_locate = QPushButton("محل پخش")
        self.btn_locate.setObjectName("Secondary")
        self.btn_locate.setCursor(Qt.PointingHandCursor)
        self.btn_locate.setIcon(icon("locate", C.muted, 16, "#FFFFFF"))
        self.btn_locate.setToolTip("نشان می‌دهد صدا همین الان کجای متن است (یک‌بار، بدون دنبال‌کردن دائم).")
        self.btn_locate.clicked.connect(lambda *_: self.locate_requested.emit())
        


        tools_row = QHBoxLayout()
        tools_row.setSpacing(7)
        tools_row.setDirection(QBoxLayout.RightToLeft)

        self.btn_edit = QPushButton("ویرایش متن")
        self.btn_edit.setObjectName("Secondary")
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setIcon(icon("edit", C.muted, 16, "#FFFFFF"))
        self.btn_edit.setToolTip("متن را در همین‌جا بنویسید یا اصلاح کنید؛ با «ذخیره» به‌عنوان متن اصلاح‌شده ثبت می‌شود.")
        self.btn_edit.clicked.connect(lambda *_: self.edit_start_requested.emit())

        self.btn_edit_save = QPushButton("ذخیره‌ی ویرایش")
        self.btn_edit_save.setObjectName("Primary")
        self.btn_edit_save.setMinimumHeight(32)
        self.btn_edit_save.setCursor(Qt.PointingHandCursor)
        self.btn_edit_save.clicked.connect(lambda *_: self.edit_save_requested.emit())

        self.btn_edit_cancel = QPushButton("انصراف")
        self.btn_edit_cancel.setObjectName("Secondary")
        self.btn_edit_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_edit_cancel.clicked.connect(lambda *_: self.edit_cancel_requested.emit())
        self.btn_edit_save.setVisible(False)
        self.btn_edit_cancel.setVisible(False)

        self.btn_colors = QPushButton("رنگ هایلایت‌ها")
        self.btn_colors.setObjectName("Secondary")
        self.btn_colors.setCursor(Qt.PointingHandCursor)
        self.btn_colors.setIcon(icon("gear", C.muted, 16, "#FFFFFF"))
        self.btn_colors.setToolTip("رنگ و شفافیت هایلایت ایرادات، کلمه‌ی در حال پخش و جستجو")
        self.btn_colors.clicked.connect(self.open_highlight_settings)

        for w in (self.btn_edit, self.btn_edit_save, self.btn_edit_cancel):
            tools_row.addWidget(w)
        tools_row.addStretch(1)
        tools_row.addWidget(self.btn_follow)
        tools_row.addWidget(self.btn_locate)
        tools_row.addWidget(self.btn_colors)
        editor_card_layout.addLayout(tools_row)

        editor_card_layout.addLayout(search_row)

        self.editor = TextEditor()
        self.editor.word_clicked.connect(self.word_clicked.emit)
        self.editor.set_highlight_style(self._load_highlight_style())
        editor_card_layout.addWidget(self.editor, 1)

        footer = QFrame()
        footer.setObjectName("EditorFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 9, 12, 9)
        footer_layout.setSpacing(10)

        legend = [
            ("ایراد باز", C.red),
            ("لنگر دستی", C.gold),
            ("کلمه‌ی در حال پخش", C.amber),
        ]
        for label_text, color in legend:
            dot = QLabel()
            dot.setFixedSize(9, 9)
            dot.setStyleSheet(f"background:{color}; border-radius:4px;")
            footer_layout.addWidget(dot)
            label = QLabel(label_text)
            label.setObjectName("Muted")
            footer_layout.addWidget(label)

        footer_layout.addStretch()
        self.lbl_stats = QLabel("")
        self.lbl_stats.setObjectName("Muted")
        footer_layout.addWidget(self.lbl_stats)
        editor_card_layout.addWidget(footer)

        editor_layout.addWidget(editor_card)
        self.main_stack.addWidget(editor_page)

        # ==========================================
        # صفحه‌های جدای مانیتورینگ و لاگ
        # ==========================================
        self.monitor_page = MonitorPage()
        self.main_stack.addWidget(self.monitor_page)

        self.log_page = LogPage()
        self.main_stack.addWidget(self.log_page)

        column.addWidget(self.main_stack, 1)
        self.nav_changed.connect(self._on_nav_page)

        center = QWidget()
        center.setObjectName("Panel")
        center.setLayout(column)
        return center

    # ==========================================
    # پنل بازرس سمت راست
    # ==========================================
    def _build_right(self):
        panel = QFrame()
        panel.setObjectName("Card")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(
            SectionLabel(
                "ایرادات",
                "target",
                C.red,
                "بررسی نقطه‌به‌نقطه‌ی متن",
            )
        )
        self.lbl_issue_count = QLabel("")
        self.lbl_issue_count.setObjectName("InspectorCount")
        header.addWidget(self.lbl_issue_count, 0, Qt.AlignTop)
        layout.addLayout(header)

        self.issues_panel = IssuesPanel()
        layout.addWidget(self.issues_panel, 1)
        return panel

    def update_issue_summary(self):
        c = self.issues_panel.counts()
        parts = [f"{fa(c.get('open', 0))} باز"]
        if c.get("resolved"):
            parts.append(f"{fa(c['resolved'])} حل‌شده")
        if c.get("missing"):
            parts.append(f"{fa(c['missing'])} پیدا نشد")
        self.lbl_issue_count.setText("  ·  ".join(parts) if self.issues_panel._records else "")

    def _active_text_widget(self):
        return self.editor

    def _apply_search(self, text):
        self.editor.set_search(str(text or "").strip())

    def _search_step(self, backward=False):
        query = self.search_edit.text().strip()
        if not query:
            return
        flags = QTextDocument.FindBackward if backward else QTextDocument.FindFlag(0)
        if not self.editor.find(query, flags):
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(query, flags)

    # ==========================================
    # ابزارهای ساخت UI
    # ==========================================
    def _plain_editor(self, read_only=False):
        editor = QPlainTextEdit()
        editor.setReadOnly(read_only)
        editor.setLayoutDirection(Qt.RightToLeft)
        option = editor.document().defaultTextOption()
        option.setTextDirection(Qt.RightToLeft)
        option.setAlignment(Qt.AlignRight)
        editor.document().setDefaultTextOption(option)
        editor.setToolTip("متن فارسی پروژه")
        return editor

    def _metric_row(self, parent_layout, title):
        row = QHBoxLayout()
        label = QLabel(title)
        label.setFixedWidth(55)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setFixedHeight(11)
        row.addWidget(label)
        row.addWidget(bar, 1)

        parent_layout.addLayout(row)
        return bar

    def _empty_state(self, title, text):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)

        icon_label = QLabel("◌")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            f"color:{C.accent2}; font-size:36px;"
        )

        title_label = QLabel(title)
        title_label.setObjectName("EmptyStateTitle")
        title_label.setAlignment(Qt.AlignCenter)

        text_label = QLabel(text)
        text_label.setObjectName("EmptyStateText")
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(icon_label)
        layout.addSpacing(6)
        layout.addWidget(title_label)
        layout.addWidget(text_label)
        layout.addStretch()
        return widget

    def refresh_action_state(self):
        self._refresh_action_state()

    def _refresh_action_state(self, *_):
        """شروع: صوت + حداقل یکی از دو متن (خام / اصلاح‌شده). ایرادات اختیاری است."""
        has_text = self.asr_row.is_loaded or self.corrected_row.is_loaded
        missing = []
        if not self.media_row.is_loaded:
            missing.append("فایل صوتی")
        if not has_text:
            missing.append("یکی از دو متن (خام یا اصلاح‌شده)")
        busy = self._running or self._editing

        self.btn_process.setEnabled(not missing and not busy)
        self.btn_apply.setVisible(self._sync_available and not self._running)
        self.btn_apply.setEnabled(self._dirty and has_text and not busy)
        any_loaded = (self.media_row.is_loaded or has_text or self.issues_row.is_loaded
                      or bool(self.issues_panel._records) or self._sync_available)
        self.btn_reset.setEnabled(any_loaded and not busy)
        self.btn_edit.setEnabled(has_text and not self._running)

        if self._running:
            self.lbl_hint.setText("")
        elif self._editing:
            self.lbl_hint.setText("در حال ویرایش متن؛ «ذخیره» یا «انصراف» را بزنید.")
        elif missing:
            self.lbl_hint.setText("برای فعال‌شدن «تحلیل» لازم است: " + "، ".join(missing))
        elif self._sync_available and self._dirty:
            self.lbl_hint.setText("متن یا ایرادات عوض شد؛ برای دیدن نتیجه «اعمال» را بزنید.")
        else:
            self.lbl_hint.setText("")

    def set_edit_mode(self, editing: bool):
        self._editing = bool(editing)
        self.btn_edit.setVisible(not editing)
        self.btn_edit_save.setVisible(editing)
        self.btn_edit_cancel.setVisible(editing)
        for w in (self.btn_follow, self.btn_locate):
            w.setEnabled(not editing)
        self._refresh_action_state()

    # ==========================================
    # رنگ هایلایت‌ها (ذخیره‌ی دائمی)
    # ==========================================
    def _load_highlight_style(self):
        style = {k: dict(v) for k, v in DEFAULT_HIGHLIGHTS.items()}
        try:
            saved = json.loads(QSettings("Natiq", "NatiqStudio").value("highlights", "{}") or "{}")
            for key in style:
                if isinstance(saved.get(key), dict):
                    style[key].update({k: saved[key][k] for k in ("color", "alpha") if k in saved[key]})
        except Exception:
            pass
        self._highlight_style = style
        return style

    def open_highlight_settings(self):
        dialog = HighlightDialog(self._highlight_style, self)

        def apply(style):
            self._highlight_style = style
            self.editor.set_highlight_style(style)
            try:
                QSettings("Natiq", "NatiqStudio").setValue("highlights", json.dumps(style))
            except Exception:
                pass

        dialog.changed.connect(apply)
        dialog.exec()

    # ==========================================
    # ریست کامل رابط
    # ==========================================
    def reset_view(self):
        for row in (self.media_row, self.asr_row, self.issues_row, self.corrected_row):
            row.clear()
        self.wave.clear_peaks()
        self.set_audio_position(0, 0)
        self.set_playing(False)
        self.editor.end_edit() if self._editing else None
        self.editor.set_paragraphs([])
        self.issues_panel.set_records([])
        self.update_issue_summary()
        self.search_edit.clear()
        self.set_process_progress(0, 100)
        self.set_pipeline_status("آماده", 0)
        self.proc_time.setText("00:00")
        self.lbl_stats.setText("")
        self._sync_available = False
        self._dirty = False
        self.set_edit_mode(False)

    def set_inputs_dirty(self, dirty: bool):
        self._dirty = bool(dirty)
        self._refresh_action_state()

    def set_media_info(self, name: str, meta: str):
        self.media_row.set_file(name, meta)
        self._refresh_action_state()

    def set_raw_info(self, name: str, meta: str):
        self.asr_row.set_file(name, meta)
        self._refresh_action_state()

    def set_issues_info(self, name: str, meta: str):
        self.issues_row.set_file(name, meta)
        self._refresh_action_state()

    def set_corrected_info(self, name: str, meta: str):
        self.corrected_row.set_file(name, meta)
        self._refresh_action_state()

    def set_waveform(self, peaks):
        self.wave.set_peaks(peaks)

    def set_audio_position(self, position_ms: int, duration_ms: int):
        self.time_lbl.setText(
            f"{ms_text(position_ms)}  /  {ms_text(duration_ms)}"
        )
        if duration_ms > 0:
            self.wave.set_progress(position_ms / duration_ms)

    def _lockable_inputs(self):
        return [
            self.cb_model, self.cb_lang, self.cb_device, self.cb_compute,
            self.tg_vad, self.tg_cond,
            self.media_row, self.asr_row, self.issues_row, self.corrected_row,
            self.btn_paste_issues,
        ]

    def set_process_running(self, running: bool):
        """حین پردازش همه‌ی تنظیمات و ورودی‌ها قفل می‌شوند؛ فقط «توقف» فعال است."""
        self._running = bool(running)
        self.btn_cancel.setVisible(self._running)
        self.btn_process.setVisible(not self._running)
        for widget in self._lockable_inputs():
            widget.setEnabled(not self._running)
        self._refresh_action_state()

    def set_sync_available(self, available: bool):
        self._sync_available = bool(available)
        self._refresh_action_state()

    def set_engine_badge(self, text: str):
        self.titlebar.model.setText(str(text))

    def set_pipeline_status(self, text, progress=None):
        self.titlebar.lbl_pipeline_status.setText(f"● {text}")
        if progress is not None:
            self.proc_bar.setValue(int(max(0, min(100, progress))))

    def set_process_progress(self, value, total=None):
        if total and total > 0:
            percent = int((value / total) * 100)
        else:
            percent = int(value)
        self.proc_bar.setValue(max(0, min(100, percent)))

    def set_gpu_status(self, text, ok=True):
        """ok: True/False یا یکی از "ok" / "warn" / "bad"."""
        level = ok if isinstance(ok, str) else ("ok" if ok else "bad")
        color = {"ok": C.green, "warn": C.amber, "bad": C.red}.get(level, C.green)
        self.titlebar.gpu.setText(str(text))
        self.titlebar.gpu.setStyleSheet(f"color:{color}; font-weight:700;")
        self.titlebar.dot.setStyleSheet(f"background:{color}; border-radius:4px;")

    def set_model_name(self, model_name: str):
        self.titlebar.model.setText(str(model_name))
        index = self.cb_model.findText(model_name)
        if index >= 0:
            self.cb_model.setCurrentIndex(index)

    def set_playing(self, playing):
        self._playing = bool(playing)
        self.btn_play.setIcon(
            icon(
                "pause" if self._playing else "play",
                "#FFFFFF",
                26,
            )
        )

    def copy_issue_template(self):
        QApplication.clipboard().setText(PROMPT)
        self.btn_copy_template.setText("کپی شد ✓")
        QTimer.singleShot(1800, lambda: self.btn_copy_template.setText("قالب Gemini"))
        self.log("پرامپت و قالب ایرادات کپی شد؛ همراه صوت و متن به Gemini بدهید.", "ok")

    def open_issues_paste_dialog(self):
        dialog = PasteDialog(
            "چسباندن لیست ایرادات",
            "هر ایراد در یک خط. نمونه:  «عبارت اشتباه» [پیشنهاد اصلاح]  یا  عبارت: توضیح",
            self,
        )
        if dialog.exec() == QDialog.Accepted and dialog.text().strip():
            self.issues_paste_requested.emit(dialog.text())

    def log(self, message, level=None):
        self.log_page.append(str(message), level or guess_level(str(message)))

    # ==========================================
    # مقایسه متن خام و اصلاح‌شده
    # ==========================================
    def settings(self):
        return {
            "model": self.cb_model.currentText(),
            "language": self.cb_lang.currentText(),
            "device": self.cb_device.currentText(),
            "compute_type": self.cb_compute.currentText(),
            "vad_filter": self.tg_vad.isChecked(),
            "condition_on_previous_text": self.tg_cond.isChecked(),
            "word_timestamps": True,
        }
