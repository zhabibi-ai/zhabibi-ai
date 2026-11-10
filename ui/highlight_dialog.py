"""تنظیم رنگ و شفافیت هایلایت‌ها (ایراد، کلمه‌ی در حال پخش، جستجو) — با پیش‌نمایش زنده."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QDialog, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout,
)

from .widgets import DEFAULT_HIGHLIGHTS, highlight_text_color

ROWS = [
    ("issue", "ایرادات"),
    ("play", "کلمه‌ی در حال پخش"),
    ("search", "جستجو"),
]


class HighlightDialog(QDialog):
    changed = Signal(dict)

    def __init__(self, style: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("PasteDialog")
        self.setWindowTitle("رنگ هایلایت‌ها")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(460)
        self.style_map = copy.deepcopy(style)
        self._controls = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        head = QLabel("رنگ هایلایت‌ها")
        head.setObjectName("PageTitle")
        lay.addWidget(head)
        note = QLabel("فقط این سه مورد هایلایت می‌شوند. تغییرات همان لحظه روی متن اعمال و ذخیره می‌شود.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)

        for key, title in ROWS:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(title)
            label.setMinimumWidth(110)
            btn = QPushButton("رنگ")
            btn.setObjectName("Secondary")
            btn.setMinimumWidth(64)
            btn.clicked.connect(lambda _=False, k=key: self._pick(k))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(10, 100)
            slider.setValue(int(self.style_map[key]["alpha"]))
            slider.valueChanged.connect(lambda v, k=key: self._alpha(k, v))
            pct = QLabel("")
            pct.setMinimumWidth(38)
            sample = QLabel("نمونه متن فارسی")
            sample.setAlignment(Qt.AlignCenter)
            sample.setMinimumWidth(120)
            row.addWidget(label)
            row.addWidget(btn)
            row.addWidget(slider, 1)
            row.addWidget(pct)
            row.addWidget(sample)
            lay.addLayout(row)
            self._controls[key] = (btn, slider, pct, sample)
            self._refresh(key)

        foot = QHBoxLayout()
        reset = QPushButton("بازنشانی به پیش‌فرض")
        reset.setObjectName("Secondary")
        reset.clicked.connect(self._reset)
        close = QPushButton("بستن")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        foot.addWidget(reset)
        foot.addStretch()
        foot.addWidget(close)
        lay.addLayout(foot)

    def _refresh(self, key):
        st = self.style_map[key]
        btn, slider, pct, sample = self._controls[key]
        col = QColor(st["color"])
        btn.setStyleSheet(f"QPushButton{{border-left:14px solid {st['color']};}}")
        pct.setText(f"{int(st['alpha'])}٪")
        slider.blockSignals(True)
        slider.setValue(int(st["alpha"]))
        slider.blockSignals(False)
        rgba = f"rgba({col.red()},{col.green()},{col.blue()},{st['alpha'] / 100:.2f})"
        sample.setStyleSheet(
            f"background:{rgba}; color:{highlight_text_color(st)}; border-radius:6px; padding:5px 8px;")

    def _emit(self):
        self.changed.emit(copy.deepcopy(self.style_map))

    def _pick(self, key):
        col = QColorDialog.getColor(QColor(self.style_map[key]["color"]), self, "انتخاب رنگ")
        if col.isValid():
            self.style_map[key]["color"] = col.name()
            self._refresh(key)
            self._emit()

    def _alpha(self, key, value):
        self.style_map[key]["alpha"] = int(value)
        self._refresh(key)
        self._emit()

    def _reset(self):
        self.style_map = copy.deepcopy(DEFAULT_HIGHLIGHTS)
        for key, _ in ROWS:
            self._refresh(key)
        self._emit()
