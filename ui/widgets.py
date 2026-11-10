"""Reusable widgets for Natiq Studio UI."""

from __future__ import annotations

import bisect

from PySide6.QtCore import Property, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QTextBlockFormat, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from .icons import icon, pixmap
from .styles import C


# ==========================================
# قالب‌بندی متن و زمان
# ==========================================
def fmt_time(sec: float) -> str:
    total = max(0, int(sec))
    if total >= 3600:
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"
    return f"{total // 60:02d}:{total % 60:02d}"


class LtrLabel(QLabel):
    """نمایش زمان، اعداد، نام مدل و سایر رشته‌های LTR."""

    def __init__(self, text="", muted=False, parent=None):
        super().__init__(str(text), parent)
        self.setLayoutDirection(Qt.LeftToRight)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setTextFormat(Qt.PlainText)
        self.setObjectName("LtrMuted" if muted else "LtrLabel")


class RtlLabel(QLabel):
    """نمایش متون فارسی با جهت RTL."""

    def __init__(self, text="", parent=None):
        super().__init__(str(text), parent)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setTextFormat(Qt.PlainText)


# ==========================================
# کنترل‌های عمومی
# ==========================================
class ElidedLabel(QLabel):
    def __init__(self, text="", mode=Qt.ElideRight, parent=None):
        super().__init__(parent)
        self._full = str(text)
        self._mode = mode
        self.setMinimumWidth(10)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setToolTip(self._full)
        self._refresh()

    def setText(self, text):
        self._full = str(text)
        self.setToolTip(self._full)
        self._refresh()

    def text(self):
        return self._full

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self):
        shown = self.fontMetrics().elidedText(
            self._full,
            self._mode,
            max(self.width() - 2, 10),
        )
        QLabel.setText(self, shown)


class Combo(QComboBox):
    """ComboBox with an explicit LTR-friendly chevron."""

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        chevron = pixmap("chevron", C.muted, 14)
        x = 8 if self.layoutDirection() == Qt.RightToLeft else self.width() - 22
        painter.drawPixmap(x, (self.height() - 14) // 2, chevron)


class ClickSlider(QSlider):
    """اسلایدر قابل‌کلیک و قابل‌کشیدن با نگاشت دقیق موقعیت ← مقدار (۰ تا ۱۰۰ کامل).

    باگ قبلی: mousePressEvent بدون فراخوانی super مصرف می‌شد، پس کشیدن (drag) اصلاً کار
    نمی‌کرد و فقط کلیک تک‌نقطه‌ای مقدار می‌گذاشت. اینجا drag، چرخ ماوس و کلید هم پشتیبانی می‌شود.
    """

    HANDLE = 16  # قطر تقریبی دستگیره

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setSingleStep(1)
        self.setPageStep(5)
        self.setFocusPolicy(Qt.StrongFocus)

    def _apply(self, x: float):
        usable = max(1, self.width() - self.HANDLE)
        ratio = max(0.0, min(1.0, (x - self.HANDLE / 2) / usable))
        value = int(round(self.minimum() + (self.maximum() - self.minimum()) * ratio))
        if value != self.value():
            self.setValue(value)
            self.sliderMoved.emit(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setSliderDown(True)
            self._apply(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown():
            self._apply(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSliderDown():
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        if steps:
            self.setValue(self.value() + int(round(steps * 5)))
        event.accept()


class Toggle(QAbstractButton):
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(42, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._t = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"t", self)
        self._anim.setDuration(150)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _get_t(self):
        return self._t

    def _set_t(self, value):
        self._t = value
        self.update()

    t = Property(float, _get_t, _set_t)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(Qt.NoPen)
        if self.isEnabled():
            left = QColor("#20372A")
            right = QColor(C.accent)
            mix = QColor(
                int(left.red() + (right.red() - left.red()) * self._t),
                int(left.green() + (right.green() - left.green()) * self._t),
                int(left.blue() + (right.blue() - left.blue()) * self._t),
            )
            painter.setBrush(mix)
        else:
            painter.setBrush(QColor("#253129"))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        diameter = rect.height() - 6
        x = rect.left() + 3 + self._t * (rect.width() - diameter - 6)
        painter.setBrush(QColor("#F4F8F5"))
        painter.drawEllipse(QRectF(x, rect.top() + 3, diameter, diameter))


class Card(QFrame):
    """Card with a shallow shadow to separate surfaces without over-glow."""

    def __init__(self, title: str | None = None, icon_name: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(13, 12, 13, 13)
        self.body.setSpacing(9)

        if title:
            header = QHBoxLayout()
            header.setSpacing(8)
            if icon_name:
                image = QLabel()
                image.setPixmap(pixmap(icon_name, C.gold, 19))
                header.addWidget(image)
            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")
            header.addWidget(title_label)
            header.addStretch()
            self.body.addLayout(header)


class SectionLabel(QWidget):
    def __init__(self, text, icon_name, color=C.gold, subtitle=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setPixmap(pixmap(icon_name, color, 18))
        layout.addWidget(icon_label)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)

        title = QLabel(text)
        title.setObjectName("SectionLabel")
        text_col.addWidget(title)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("SectionLabelSubtle")
            text_col.addWidget(sub)

        layout.addLayout(text_col)
        layout.addStretch()


class InfoDot(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__("ⓘ", parent)
        self.setObjectName("InfoDot")
        self.setToolTip(text)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.WhatsThisCursor)
        self.setFixedSize(18, 18)


# ==========================================
# ورودی فایل و وضعیت بارگذاری
# ==========================================
class FileRow(QFrame):
    clicked = Signal()
    removed = Signal()

    def __init__(self, icon_name="file", placeholder="انتخاب فایل...", parent=None):
        super().__init__(parent)
        self.setObjectName("FileRow")
        self.setCursor(Qt.PointingHandCursor)
        self._placeholder = placeholder
        self._loaded = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(10)

        icon_box = QLabel()
        icon_box.setObjectName("FileIcon")
        icon_box.setFixedSize(42, 42)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(pixmap(icon_name, C.accent2, 21))
        layout.addWidget(icon_box)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.name = ElidedLabel("")
        self.name.setObjectName("FileName")
        self.name.setLayoutDirection(Qt.RightToLeft)
        self.name.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.meta = LtrLabel("", muted=True)
        self.meta.setObjectName("FileMeta")

        text_col.addWidget(self.name)
        text_col.addWidget(self.meta)
        layout.addLayout(text_col, 1)

        self.x = QToolButton()
        self.x.setIcon(icon("close", C.muted, 14, C.text))
        self.x.setIconSize(QSize(14, 14))
        self.x.setToolTip("حذف از پروژه")
        self.x.clicked.connect(self.removed)
        layout.addWidget(self.x, 0, Qt.AlignTop)

        self.clear()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def set_file(self, name: str, meta: str = "بارگذاری شد"):
        self._loaded = True
        self.name.setText(name)
        self.meta.setText(meta)
        self.x.show()
        self.setProperty("loaded", True)
        self.style().unpolish(self)
        self.style().polish(self)

    def clear(self):
        self._loaded = False
        self.name.setText(self._placeholder)
        self.meta.setText("")
        self.x.hide()
        self.setProperty("loaded", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


# ==========================================
# موج صوتی تعاملی
# ==========================================
class WaveformWidget(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self._peaks: list[float] = []
        self._progress = 0.0
        self._has_data = False
        self._loading = False
        self._cache_key = None
        self._cache: list[float] = []

    def set_peaks(self, peaks):
        self._peaks = list(peaks or [])
        self._has_data = bool(self._peaks)
        self._loading = False
        self._cache_key = None
        self.update()

    def set_loading(self, loading: bool):
        self._loading = bool(loading)
        self.update()

    def clear_peaks(self):
        self._peaks.clear()
        self._has_data = False
        self._progress = 0.0
        self._cache_key = None
        self.update()

    def set_progress(self, progress: float):
        self._progress = max(0.0, min(1.0, float(progress)))
        self.update()

    def _bars(self, count):
        key = (count, len(self._peaks))
        if key != self._cache_key:
            n = len(self._peaks)
            out = []
            for i in range(count):
                a = int(i * n / count)
                b = max(a + 1, int((i + 1) * n / count))
                out.append(max(self._peaks[a:b]))
            self._cache, self._cache_key = out, key
        return self._cache

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width, height = max(1, self.width()), max(1, self.height())
        step, bar_width = 3, 1.9
        count = max(1, width // step)
        bars = self._bars(count) if self._has_data else [0.07] * count
        played = int(count * self._progress)

        painter.setPen(QPen(QColor("#1D3328"), 1))
        painter.drawLine(0, height // 2, width, height // 2)
        painter.setPen(Qt.NoPen)
        for index, value in enumerate(bars):
            bar_height = max(3.0, value * height * 0.86)
            if not self._has_data:
                color = QColor("#1D3429")
            elif index < played:
                color = QColor(C.gold)
            else:
                color = QColor("#7D6D3C")
            painter.setBrush(color)
            painter.drawRoundedRect(
                QRectF(index * step + (step - bar_width) / 2, (height - bar_height) / 2, bar_width, bar_height),
                1.0, 1.0)

        if self._loading and not self._has_data:
            painter.setPen(QColor(C.muted))
            painter.drawText(self.rect(), Qt.AlignCenter, "در حال تحلیل موج صوتی…")

        cursor_x = max(0, min(width - 1, int(self._progress * width)))
        painter.setPen(QPen(QColor(C.accent2), 2))
        painter.drawLine(cursor_x, 1, cursor_x, height - 1)
        painter.setPen(QPen(QColor("#0B1511"), 2))
        painter.setBrush(QColor(C.accent2))
        painter.drawEllipse(QRectF(cursor_x - 5, height / 2 - 5, 10, 10))

    def _seek_from(self, x):
        ratio = max(0.0, min(1.0, x / max(1, self.width())))
        self._progress = ratio
        self.update()
        self.seek_requested.emit(ratio)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._seek_from(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._seek_from(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)


class TimelineBar(QWidget):
    """نوار زمان: رنگ هر بخش = وضعیت آن؛ نشانگر طلایی = لنگر دستی؛ کلیک = پرش در صوت."""

    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)
        self.setCursor(Qt.PointingHandCursor)
        self._segments, self._anchors, self._duration, self._pos = [], [], 0.0, 0.0

    def set_data(self, segments, anchors, duration):
        self._segments, self._anchors = list(segments or []), list(anchors or [])
        self._duration = max(0.0, float(duration or 0.0))
        self.update()

    def set_position(self, seconds):
        self._pos = float(seconds)
        self.update()

    def _span(self):
        end = max([s["end"] for s in self._segments] + [0.0])
        return max(self._duration, end, 0.001)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#0B1712"))
        painter.drawRoundedRect(QRectF(0, 8, w, h - 16), 7, 7)
        span = self._span()
        for seg in self._segments:
            color = QColor(STATUS_INFO.get(seg.get("status", "confirmed"), STATUS_INFO["confirmed"])[1])
            color.setAlpha(190)
            x0 = seg["start"] / span * w
            x1 = max(x0 + 2, seg["end"] / span * w)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x0, 12, x1 - x0 - 1, h - 24), 3, 3)
        painter.setBrush(QColor(C.gold))
        for t in self._anchors:
            x = t / span * w
            painter.drawPolygon([QPointF(x - 5, h - 2), QPointF(x + 5, h - 2), QPointF(x, h - 11)])
        px = max(0.0, min(w - 1.0, self._pos / span * w))
        painter.setPen(QPen(QColor(C.white), 2))
        painter.drawLine(int(px), 4, int(px), h - 4)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.width() > 0:
            self.seek_requested.emit(event.position().x() / self.width() * self._span())
            event.accept()
            return
        super().mousePressEvent(event)


# ==========================================
# ویرایشگر متن RTL با Highlight و Search
# ==========================================
class _Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


MOD_CTRL, MOD_ALT, MOD_SHIFT = 1, 2, 4

# فقط سه چیز هایلایت می‌شود: ایرادات، کلمه‌ی در حال پخش، نتایج جستجو.
DEFAULT_HIGHLIGHTS = {
    "issue":  {"color": "#E5484D", "alpha": 70},
    "play":   {"color": "#E6C97A", "alpha": 60},
    "search": {"color": "#FFD54A", "alpha": 100},
}
_EDITOR_BG = (13, 25, 20)


def highlight_text_color(st: dict) -> str:
    """رنگ متن روی هایلایت: بر اساس روشنایی رنگ ترکیب‌شده با پس‌زمینه، تیره یا روشن."""
    c = QColor(st["color"])
    a = max(0.0, min(1.0, st["alpha"] / 100.0))
    r = c.red() * a + _EDITOR_BG[0] * (1 - a)
    g = c.green() * a + _EDITOR_BG[1] * (1 - a)
    b = c.blue() * a + _EDITOR_BG[2] * (1 - a)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return "#10140F" if luminance > 0.42 else "#FFFFFF"


def _mod_flags(mods) -> int:
    flags = 0
    if mods & Qt.KeyboardModifier.ControlModifier or mods & Qt.KeyboardModifier.MetaModifier:
        flags |= MOD_CTRL
    if mods & Qt.KeyboardModifier.AltModifier:
        flags |= MOD_ALT
    if mods & Qt.KeyboardModifier.ShiftModifier:
        flags |= MOD_SHIFT
    return flags


class TextEditor(QPlainTextEdit):
    """ادیتور فارسی با شماره خط، Highlight، Search و لنگر کلمه.

    word_clicked(word_id, modifiers): modifiers = ترکیب MOD_CTRL / MOD_ALT / MOD_SHIFT
    word_action(word_id, action):  "play" | "anchor" | "unanchor"
    """

    word_clicked = Signal(int, int)
    word_action = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        # ویرایش مستقیم این نما، نگاشت کلمه↔زمان را خراب می‌کند؛ ویرایش در تب «متن خام» انجام می‌شود.
        self.setReadOnly(True)

        option = self.document().defaultTextOption()
        option.setTextDirection(Qt.RightToLeft)
        option.setAlignment(Qt.AlignRight)
        self.document().setDefaultTextOption(option)

        self._spans: list[tuple[int, int]] = []
        self._starts: list[int] = []
        self._style = {k: dict(v) for k, v in DEFAULT_HIGHLIGHTS.items()}
        self._word_status: list[str] = []
        self._active_id = -1
        self._focus_ids: list[int] = []
        self._search_text = ""
        self._editing = False
        # انتخاب جاری (مورد فعلی جستجو) هم پررنگ و واضح باشد
        self.setStyleSheet("QPlainTextEdit{selection-background-color:#E6A84D; selection-color:#10140F;}")

        self._gutter = _Gutter(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._on_update_request)
        self._update_margin()

    # ==========================================
    # شماره خطوط
    # ==========================================
    def gutter_width(self):
        return 16 + self.fontMetrics().horizontalAdvance("00") + 14

    def _update_margin(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _on_update_request(self, rect, dy):
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        content = self.contentsRect()
        self._gutter.setGeometry(QRect(content.left(), content.top(), self.gutter_width(), content.height()))

    def paint_gutter(self, event):
        painter = QPainter(self._gutter)
        width = self._gutter.width()
        painter.setPen(QColor(C.border))
        painter.drawLine(width - 1, event.rect().top(), width - 1, event.rect().bottom())
        painter.setPen(QColor(C.muted))

        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        font_height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(0, top + 6, width - 12, font_height,
                                 Qt.AlignRight | Qt.AlignVCenter, f"{number + 1:02d}")
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    # ==========================================
    # وضعیت کلمات
    # ==========================================
    def _hl(self, key, alpha=None):
        st = dict(self._style[key])
        if alpha is not None:
            st["alpha"] = alpha
        col = QColor(st["color"])
        col.setAlphaF(max(0.0, min(1.0, st["alpha"] / 100.0)))
        return col, QColor(highlight_text_color(st))

    def _fmt(self, status: str) -> QTextCharFormat:
        """فقط «issue» رنگی است؛ بقیه‌ی کلمات متن عادی‌اند."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(C.text))
        if status == "issue":
            bg, fg = self._hl("issue")
            fmt.setBackground(bg)
            fmt.setForeground(fg)
        return fmt

    def set_highlight_style(self, style: dict):
        for key in self._style:
            if key in style:
                self._style[key].update(style[key])
        for i, status in enumerate(self._word_status):
            if status != "confirmed":
                self.set_word_status(i, status)
        self._apply()

    def set_paragraphs(self, paragraphs):
        self.clear()
        self._spans.clear()
        self._starts.clear()
        self._word_status = []
        self._active_id = -1
        self._focus_ids = []

        block_format = QTextBlockFormat()
        block_format.setLineHeight(185, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        block_format.setAlignment(Qt.AlignRight)
        block_format.setLayoutDirection(Qt.RightToLeft)
        block_format.setBottomMargin(15)

        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        for index, paragraph in enumerate(paragraphs):
            if index == 0:
                cursor.setBlockFormat(block_format)
            else:
                cursor.insertBlock(block_format)
            for word, status in paragraph:
                start = cursor.position()
                cursor.insertText(word, self._fmt(status))
                self._spans.append((start, cursor.position()))
                self._word_status.append(status)
                self._starts.append(start)
                cursor.insertText(" ", self._fmt("confirmed"))
        cursor.endEditBlock()
        self.moveCursor(QTextCursor.Start)

    def set_word_status(self, word_id: int, status: str):
        if 0 <= word_id < len(self._spans):
            if word_id < len(self._word_status):
                self._word_status[word_id] = status
            start, end = self._spans[word_id]
            cursor = QTextCursor(self.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.setCharFormat(self._fmt(status))

    def word_at(self, position: int) -> int:
        index = bisect.bisect_right(self._starts, position) - 1
        if 0 <= index < len(self._spans) and position <= self._spans[index][1]:
            return index
        return -1

    def caret_word(self) -> int:
        return self.word_at(self.textCursor().position())

    # ==========================================
    # تعامل ماوس و کیبورد
    #   Ctrl+Click : پخش صدا از همین کلمه
    #   Alt+Click  : «صدا همین‌جاست» — ثبت لنگر دستی
    #   F2 / F3    : لنگر / پخش برای کلمه‌ی زیر مکان‌نما
    # ==========================================
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton and not self._editing:
            position = self.cursorForPosition(event.position().toPoint()).position()
            word_id = self.word_at(position)
            if word_id >= 0:
                self.word_clicked.emit(word_id, _mod_flags(event.modifiers()))

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_F2, Qt.Key_F3) and not self._editing:
            word_id = self.caret_word()
            if word_id >= 0:
                self.word_action.emit(word_id, "anchor" if key == Qt.Key_F2 else "play")
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        if self._editing:
            return super().contextMenuEvent(event)
        word_id = self.word_at(self.cursorForPosition(event.pos()).position())
        menu = QMenu(self)
        actions = {}
        if word_id >= 0:
            actions[menu.addAction("▶   پخش صدا از این کلمه        (Ctrl+Click)")] = "play"
            actions[menu.addAction("📍  صدا همین‌جاست — ثبت لنگر   (Alt+Click / F2)")] = "anchor"
            actions[menu.addAction("✕   حذف لنگر دستی این کلمه")] = "unanchor"
            menu.addSeparator()
        copy = menu.addAction("کپی")
        copy.setEnabled(self.textCursor().hasSelection())
        chosen = menu.exec(event.globalPos())
        if chosen is copy:
            self.copy()
        elif chosen in actions:
            self.word_action.emit(word_id, actions[chosen])

    # ==========================================
    # Search و follower
    # ==========================================
    def _selection(self, start, end, key, alpha=None, underline=False):
        bg, fg = self._hl(key, alpha)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = QTextCursor(self.document())
        selection.cursor.setPosition(start)
        selection.cursor.setPosition(end, QTextCursor.KeepAnchor)
        selection.format.setBackground(bg)
        selection.format.setForeground(fg)
        if underline:
            selection.format.setFontUnderline(True)
        return selection

    def _apply(self):
        """ترتیب لایه‌ها: ایراد انتخاب‌شده ← کلمه‌ی در حال پخش ← جستجو (جستجو همیشه روی همه)."""
        sels = []
        ids = [i for i in self._focus_ids if 0 <= i < len(self._spans)]
        if ids and not self._editing:
            sels.append(self._selection(self._spans[ids[0]][0], self._spans[ids[-1]][1], "issue", 100, True))
        if 0 <= self._active_id < len(self._spans) and not self._editing:
            start, end = self._spans[self._active_id]
            sels.append(self._selection(start, end, "play"))
        q = self._search_text
        if q:
            doc, pos = self.document(), 0
            while True:
                cur = doc.find(q, pos)
                if cur.isNull():
                    break
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cur
                bg, fg = self._hl("search")
                sel.format.setBackground(bg)
                sel.format.setForeground(fg)
                sels.append(sel)
                if cur.position() <= pos:
                    break
                pos = cur.position()
        self.setExtraSelections(sels)

    def set_active_word(self, word_id: int, scroll=True):
        self._active_id = word_id
        if scroll and 0 <= word_id < len(self._spans):
            cursor = QTextCursor(self.document())
            cursor.setPosition(self._spans[word_id][0])
            rect = self.cursorRect(cursor)
            if not self.viewport().rect().contains(rect):
                bar = self.verticalScrollBar()
                bar.setValue(bar.value() + rect.top() - self.viewport().height() // 3)
        self._apply()

    def set_focus_span(self, word_ids):
        """ایراد انتخاب‌شده: کل بازه پررنگ و زیرخط‌دار."""
        self._focus_ids = list(word_ids or [])
        self._apply()

    def clear_active(self):
        self._active_id = -1
        self._apply()

    def scroll_to_word(self, word_id: int):
        """کلمه را وسط نما می‌آورد و مکان‌نما را روی آن می‌گذارد (برای F2 بعدی)."""
        if 0 <= word_id < len(self._spans):
            cursor = QTextCursor(self.document())
            cursor.setPosition(self._spans[word_id][0])
            self.setTextCursor(cursor)
            self.centerCursor()

    def set_search(self, text: str):
        self._search_text = str(text).strip()
        self._apply()

    # ==========================================
    # حالت ویرایش
    # ==========================================
    def begin_edit(self, paragraphs):
        """متن ساده (بدون رنگ) نمایش داده می‌شود و قابل‌نوشتن است."""
        self._editing = True
        self.set_paragraphs(paragraphs)
        self.setReadOnly(False)
        self._apply()
        self.setFocus()

    def end_edit(self) -> str:
        text = self.toPlainText()
        self._editing = False
        self.setReadOnly(True)
        return text


# ==========================================
# Segmentها
# ==========================================
STATUS_INFO = {
    "confirmed": ("تأیید شده", C.green, "check"),
    "changed": ("تغییر یافته", C.amber, "edit"),
    "added": ("افزوده شده", C.red, "plus"),
    "needs_review": ("نیاز به بررسی", C.gold, "target"),
    "guessed": ("زمان تخمینی", C.grey, "clock"),
}


class SegmentItem(QFrame):
    clicked = Signal(int)

    def __init__(self, segment: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("SegItem")
        self.setCursor(Qt.PointingHandCursor)
        self.index = segment["index"]

        label, color, _ = STATUS_INFO.get(segment.get("status", "confirmed"), STATUS_INFO["confirmed"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 10, 5)
        layout.setSpacing(9)

        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background:{color}; border-radius:2px;")
        layout.addWidget(bar)

        content = QVBoxLayout()
        content.setContentsMargins(0, 5, 0, 5)
        content.setSpacing(5)

        header = QHBoxLayout()
        time = LtrLabel(f"{fmt_time(segment['start'])} – {fmt_time(segment['end'])}", muted=True)
        time.setObjectName("SegTime")
        header.addWidget(time)
        header.addStretch()

        badge = QLabel(label)
        badge.setObjectName("StatusPill")
        badge.setStyleSheet(
            f"color:{color}; background:{QColor(color).darker(500).name()};"
            "border-radius:8px; padding:2px 8px; font-size:10px; font-weight:700;"
        )
        header.addWidget(badge)
        content.addLayout(header)

        text = ElidedLabel(segment["text"], Qt.ElideRight)
        text.setObjectName("SegText")
        text.setLayoutDirection(Qt.RightToLeft)
        content.addWidget(text)
        layout.addLayout(content, 1)

        number = LtrLabel(str(segment["index"]))
        number.setObjectName("SegNum")
        number.setAlignment(Qt.AlignCenter)
        number.setFixedSize(24, 24)
        layout.addWidget(number, 0, Qt.AlignTop)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)
            event.accept()
            return
        super().mousePressEvent(event)


class SegmentList(QScrollArea):
    segment_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)
        layout.addStretch()
        self.setWidget(host)
        self._layout = layout
        self._items: dict[int, SegmentItem] = {}

    def set_segments(self, segments):
        for item in self._items.values():
            item.deleteLater()
        self._items.clear()
        for segment in segments:
            item = SegmentItem(segment)
            item.clicked.connect(self.segment_selected)
            item.clicked.connect(self.select)
            self._layout.insertWidget(self._layout.count() - 1, item)
            self._items[segment["index"]] = item

    def select(self, index: int):
        for item_index, item in self._items.items():
            item.set_selected(item_index == index)
        if index in self._items:
            self.ensureWidgetVisible(self._items[index])

    def clear(self):
        self.set_segments([])
