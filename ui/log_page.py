"""صفحه‌ی لاگ عملیات (جدا از مانیتورینگ)."""
from __future__ import annotations

import html
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from .icons import icon
from .styles import C
from .widgets import Card, SectionLabel

LEVELS = {
    "info": ("اطلاعات", C.text),
    "ok": ("موفق", C.green),
    "warn": ("هشدار", C.amber),
    "error": ("خطا", C.red),
}


def guess_level(message: str) -> str:
    m = message.lstrip()
    if m.startswith(("خطا", "✕", "❌")):
        return "error"
    if m.startswith(("⚠", "هشدار")):
        return "warn"
    if m.startswith(("✓", "✔")):
        return "ok"
    return "info"


class LogPage(QWidget):
    export_requested = Signal()

    MAX_ENTRIES = 5000

    def __init__(self):
        super().__init__()
        self.entries: list[tuple[str, str, str]] = []
        self._filter = "all"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        card = Card()
        root.addWidget(card)
        lay = card.body

        lay.addWidget(SectionLabel("گزارش عملیات", "list", C.gold,
                                   "رویدادهای پردازش، هشدارها و خطاها"))

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for key, text in (("all", "همه"), ("info", "اطلاعات"), ("warn", "هشدار"), ("error", "خطا")):
            b = QPushButton(text)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setChecked(key == "all")
            b.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            self.group.addButton(b)
            self.buttons[key] = b
            bar.addWidget(b)

        self.search = QLineEdit()
        self.search.setObjectName("SearchBar")
        self.search.setPlaceholderText("جستجو در لاگ...")
        self.search.setLayoutDirection(Qt.RightToLeft)
        self.search.textChanged.connect(lambda _: self.render())
        bar.addWidget(self.search, 1)

        btn_clear = QPushButton("پاک‌کردن")
        btn_clear.setObjectName("Secondary")
        btn_clear.setIcon(icon("trash", C.muted, 16))
        btn_clear.clicked.connect(self.clear)
        bar.addWidget(btn_clear)

        btn_export = QPushButton("ذخیره‌ی لاگ")
        btn_export.setObjectName("Primary")
        btn_export.setIcon(icon("download", "#FFFFFF", 16))
        btn_export.setMinimumHeight(32)
        btn_export.clicked.connect(lambda *_: self.export_requested.emit())
        bar.addWidget(btn_export)
        lay.addLayout(bar)

        self.view = QTextEdit()
        self.view.setObjectName("LogBox")
        self.view.setReadOnly(True)
        self.view.setLayoutDirection(Qt.RightToLeft)
        lay.addWidget(self.view, 1)

    # ---- API ----
    def append(self, message: str, level: str | None = None):
        level = level or guess_level(message)
        entry = (time.strftime("%H:%M:%S"), level if level in LEVELS else "info", str(message))
        self.entries.append(entry)
        if len(self.entries) > self.MAX_ENTRIES:
            del self.entries[:500]
            self.render()
            return
        if self._matches(entry):
            self.view.append(self._html(entry))
        self._update_counts()

    def clear(self):
        self.entries.clear()
        self.view.clear()
        self._update_counts()

    def as_text(self) -> str:
        return "\n".join(f"[{t}] [{lvl.upper()}] {msg}" for t, lvl, msg in self.entries) + "\n"

    # ---- داخلی ----
    def _set_filter(self, key):
        self._filter = key
        self.render()

    def _matches(self, entry):
        _, level, msg = entry
        if self._filter != "all" and level != self._filter:
            return False
        q = self.search.text().strip()
        return not q or q in msg

    @staticmethod
    def _html(entry):
        t, level, msg = entry
        color = LEVELS[level][1]
        return (f'<p dir="rtl" style="margin:2px 0;"><span style="color:{C.subtle}">\u200e[{t}]\u200e</span> '
                f'<span style="color:{color}">{html.escape(msg)}</span></p>')

    def render(self):
        self.view.setUpdatesEnabled(False)
        self.view.clear()
        for entry in self.entries:
            if self._matches(entry):
                self.view.append(self._html(entry))
        self.view.setUpdatesEnabled(True)
        self._update_counts()

    def _update_counts(self):
        counts = {"warn": 0, "error": 0}
        for _, lvl, _m in self.entries:
            if lvl in counts:
                counts[lvl] += 1
        self.buttons["warn"].setText(f"هشدار ({counts['warn']})" if counts["warn"] else "هشدار")
        self.buttons["error"].setText(f"خطا ({counts['error']})" if counts["error"] else "خطا")
