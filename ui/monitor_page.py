"""صفحه‌ی مانیتورینگ سخت‌افزار (جدا از لاگ)."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.hardware import (
    METRIC_INFO, STAGE_LABELS, level_for_percent, level_for_temp,
)
from .icons import icon, pixmap
from .styles import C
from .widgets import Card, LtrLabel, SectionLabel

LEVEL_COLOR = {"ok": C.green, "warn": C.amber, "bad": C.red, "na": C.subtle}
LEVEL_TEXT = {"ok": "نرمال", "warn": "گرم / سنگین", "bad": "بحرانی", "na": "در دسترس نیست"}

SERIES = [
    ("cpu", "CPU", C.accent2),
    ("ram", "RAM", C.purple),
    ("gpu_util", "GPU", C.gold),
    ("vram_pct", "VRAM", C.amber),
    ("gpu_temp", "دمای GPU", C.red),
]


def _f(value, digits=0, suffix=""):
    return "—" if value is None else f"{value:.{digits}f}{suffix}"


# ==========================================
# کارت یک شاخص
# ==========================================
class MetricCard(QFrame):
    def __init__(self, title, icon_name, color):
        super().__init__()
        self.setObjectName("MetricCard")
        self._color = color
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(7)
        img = QLabel()
        img.setPixmap(pixmap(icon_name, color, 17))
        head.addWidget(img)
        t = QLabel(title)
        t.setObjectName("MetricTitle")
        head.addWidget(t)
        head.addStretch()
        self.state = QLabel("")
        self.state.setStyleSheet(f"color:{C.subtle}; font-size:10.5px; font-weight:700;")
        head.addWidget(self.state)
        lay.addLayout(head)

        self.value = LtrLabel("—")
        self.value.setObjectName("MetricValue")
        lay.addWidget(self.value)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)

        self.sub = QLabel("")
        self.sub.setObjectName("MetricSub")
        lay.addWidget(self.sub)

    def set_value(self, text, percent=None, sub="", level="ok"):
        color = LEVEL_COLOR.get(level, self._color)
        if level == "na":
            text, percent = "—", 0
        self.value.setText(text)
        self.bar.setValue(int(max(0, min(100, percent or 0))))
        self.bar.setStyleSheet(
            f"QProgressBar::chunk{{background:{color}; border-radius:4px;}}")
        self.state.setText(LEVEL_TEXT.get(level, ""))
        self.state.setStyleSheet(f"color:{color}; font-size:10.5px; font-weight:700;")
        self.sub.setText(sub)


# ==========================================
# نمودار تاریخچه
# ==========================================
class HistoryChart(QWidget):
    def __init__(self, maxlen=300):
        super().__init__()
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.maxlen = maxlen
        self.points = deque(maxlen=maxlen)
        self.visible = {k: True for k, _, _ in SERIES}

    def push(self, stats, stage):
        row = {k: stats.get(k) for k, _, _ in SERIES}
        row["stage"] = stage
        self.points.append(row)
        self.update()

    def set_visible(self, key, on):
        self.visible[key] = bool(on)
        self.update()

    def clear(self):
        self.points.clear()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        L, R, T, B = 36, 12, 10, 22
        pw, ph = max(1, w - L - R), max(1, h - T - B)

        p.setPen(QPen(QColor("#1B3025"), 1))
        for v in (0, 25, 50, 75, 100):
            y = T + ph - ph * v / 100
            p.drawLine(L, int(y), w - R, int(y))
        p.setPen(QColor(C.subtle))
        for v in (0, 50, 100):
            y = T + ph - ph * v / 100
            p.drawText(0, int(y) - 8, L - 6, 16, Qt.AlignRight | Qt.AlignVCenter, str(v))
        p.drawText(L, h - 18, pw, 16, Qt.AlignRight | Qt.AlignVCenter, "۵ دقیقه‌ی اخیر  ←  اکنون")

        n = len(self.points)
        if n < 2:
            p.setPen(QColor(C.muted))
            p.drawText(self.rect(), Qt.AlignCenter, "در انتظار داده…")
            return
        dx = pw / (self.maxlen - 1)

        # باند مراحل پردازش
        start = 0
        for i in range(1, n + 1):
            if i == n or self.points[i]["stage"] != self.points[start]["stage"]:
                stage = self.points[start]["stage"]
                if stage != "idle":
                    band = QColor(C.gold)
                    band.setAlpha(26)
                    p.setPen(Qt.NoPen)
                    p.setBrush(band)
                    x0 = L + start * dx
                    p.drawRect(QRectF(x0, T, max(2.0, (i - 1 - start) * dx), ph))
                    p.setPen(QColor(C.gold))
                    p.drawText(int(x0) + 4, T + 2, 160, 14, Qt.AlignLeft, STAGE_LABELS.get(stage, stage))
                start = i

        for key, _, color in SERIES:
            if not self.visible.get(key):
                continue
            p.setPen(QPen(QColor(color), 1.8))
            prev = None
            for i, row in enumerate(self.points):
                v = row.get(key)
                if v is None:
                    prev = None
                    continue
                pt = (L + i * dx, T + ph - ph * max(0, min(100, v)) / 100)
                if prev:
                    p.drawLine(int(prev[0]), int(prev[1]), int(pt[0]), int(pt[1]))
                prev = pt


# ==========================================
# صفحه‌ی اصلی
# ==========================================
class MonitorPage(QWidget):
    export_requested = Signal(str)     # csv | json | txt
    reset_requested = Signal()

    ROWS = ["cpu", "ram", "gpu_util", "vram_pct", "gpu_temp", "cpu_temp", "gpu_power_w"]

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        inner = QWidget()
        inner.setObjectName("Panel")
        scroll.setWidget(inner)

        root = QVBoxLayout(inner)
        root.setContentsMargins(0, 0, 8, 0)
        root.setSpacing(12)

        head = QHBoxLayout()
        head.addWidget(SectionLabel("مانیتورینگ سخت‌افزار", "activity", C.gold,
                                    "وضعیت لحظه‌ای، تاریخچه‌ی این نشست و گزارش عملکرد"))
        head.addStretch()
        self.lbl_gpu = LtrLabel("GPU: —", muted=True)
        head.addWidget(self.lbl_gpu)
        root.addLayout(head)

        cards = QGridLayout()
        cards.setSpacing(10)
        self.c_cpu = MetricCard("پردازنده (CPU)", "cpu", C.accent2)
        self.c_ram = MetricCard("حافظه RAM", "list", C.purple)
        self.c_gpu = MetricCard("بار GPU", "bolt", C.gold)
        self.c_vram = MetricCard("حافظه GPU (VRAM)", "music", C.amber)
        self.c_temp = MetricCard("دمای GPU", "thermo", C.red)
        self.c_pow = MetricCard("توان / ساعت GPU", "activity", C.green)
        for n, c in enumerate((self.c_cpu, self.c_ram, self.c_gpu, self.c_vram, self.c_temp, self.c_pow)):
            c.setMinimumHeight(112)
            cards.addWidget(c, n // 3, n % 3)
        for col in range(3):
            cards.setColumnStretch(col, 1)
        root.addLayout(cards)

        chart_card = Card("تاریخچه‌ی زنده", "wave")
        toggles = QHBoxLayout()
        toggles.setSpacing(6)
        self.chart = HistoryChart()
        for key, label, color in SERIES:
            b = QPushButton(label)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setChecked(True)
            b.setStyleSheet(f"QPushButton:checked{{border-color:{color}; color:{color};}}")
            b.toggled.connect(lambda on, k=key: self.chart.set_visible(k, on))
            toggles.addWidget(b)
        toggles.addStretch()
        chart_card.body.addLayout(toggles)
        chart_card.body.addWidget(self.chart, 1)
        chart_card.setMinimumHeight(300)
        root.addWidget(chart_card)

        bottom = QVBoxLayout()
        bottom.setSpacing(12)

        sum_card = Card("خلاصه‌ی کل نشست", "target")
        self.tbl_sum = self._table(["شاخص", "کمینه", "میانگین", "بیشینه", "زمان اوج"])
        self.tbl_sum.setFixedHeight(34 + 32 * len(self.ROWS) + 6)
        sum_card.body.addWidget(self.tbl_sum, 1)
        bottom.addWidget(sum_card)

        stage_card = Card("عملکرد مراحل پردازش", "sparkle")
        self.tbl_stage = self._table(["مرحله", "مدت", "GPU میانگین", "VRAM بیشینه", "دما بیشینه"])
        self.tbl_stage.setFixedHeight(34 + 32 + 6)
        stage_card.body.addWidget(self.tbl_stage, 1)
        self.lbl_warn = QLabel("")
        self.lbl_warn.setWordWrap(True)
        self.lbl_warn.setTextFormat(Qt.PlainText)
        self.lbl_warn.setStyleSheet(f"color:{C.amber}; font-size:11.5px;")
        stage_card.body.addWidget(self.lbl_warn)
        bottom.addWidget(stage_card)
        root.addLayout(bottom)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("Muted")
        root.addWidget(self.lbl_meta)
        foot = QHBoxLayout()
        foot.setSpacing(8)
        foot.addStretch()
        for kind, text in (("txt", "گزارش TXT"), ("json", "گزارش JSON"), ("csv", "داده‌ی CSV")):
            b = QPushButton(text)
            b.setObjectName("Primary" if kind == "txt" else "Secondary")
            b.setIcon(icon("download", "#FFFFFF" if kind == "txt" else C.muted, 16))
            b.setToolTip({"txt": "گزارش خوانا با خلاصه، مراحل و هشدارها",
                          "json": "خلاصه + همه‌ی نمونه‌ها برای تحلیل دقیق",
                          "csv": "تک‌تک نمونه‌ها؛ قابل‌باز شدن در Excel"}[kind])
            b.clicked.connect(lambda _=False, k=kind: self.export_requested.emit(k))
            foot.addWidget(b)
        btn_reset = QPushButton("شروع نشست جدید")
        btn_reset.setObjectName("Danger")
        btn_reset.setIcon(icon("refresh", C.red, 16))
        btn_reset.setToolTip("پاک‌کردن تاریخچه و شروع ثبت از نو")
        btn_reset.clicked.connect(lambda *_: self.reset_requested.emit())
        foot.addWidget(btn_reset)
        root.addLayout(foot)
        root.addStretch()

    @staticmethod
    def _table(headers):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection)
        t.setShowGrid(False)
        t.setLayoutDirection(Qt.RightToLeft)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.verticalHeader().setDefaultSectionSize(32)
        t.horizontalHeader().setFixedHeight(34)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return t

    # ---- داده‌ی زنده ----
    def update_stats(self, s, stage):
        self.chart.push(s, stage)
        self.lbl_gpu.setText(f"GPU: {s['gpu_name']}" if s.get("has_gpu") else "GPU: یافت نشد (پردازش روی CPU)")
        cpu_t = s.get("cpu_temp")
        self.c_cpu.set_value(_f(s["cpu"], 0, "٪").replace("٪", "%"), s["cpu"],
                             f"برنامه: {s['app_cpu']:.0f}%" + (f"  |  دما: {cpu_t:.0f}°C" if cpu_t is not None else ""))
        self.c_ram.set_value(f"{s['ram']:.0f}%", s["ram"],
                             f"{s['ram_used_gb']:.1f} / {s['ram_total_gb']:.1f} GB  |  برنامه: {s['app_ram_mb'] / 1024:.2f} GB",
                             level_for_percent(s["ram"]))
        if not s.get("has_gpu"):
            for c in (self.c_gpu, self.c_vram, self.c_temp, self.c_pow):
                c.set_value("—", 0, "GPU شناسایی نشد", "na")
            return
        self.c_gpu.set_value(_f(s["gpu_util"], 0, "%"), s["gpu_util"], "", "ok" if s["gpu_util"] is not None else "na")
        used, total = s["vram_used_mb"], s["vram_total_mb"]
        self.c_vram.set_value(_f(s["vram_pct"], 0, "%"), s["vram_pct"],
                              f"{used / 1024:.1f} / {total / 1024:.1f} GB" if used is not None and total else "",
                              level_for_percent(s["vram_pct"]))
        t = s["gpu_temp"]
        self.c_temp.set_value(_f(t, 0, "°C"), t, "", level_for_temp(t))
        pw = s["gpu_power_w"]
        clk = s["gpu_clock_mhz"]
        self.c_pow.set_value(_f(pw, 0, " W"), min(100, (pw or 0) / 4.5) if pw is not None else 0,
                             f"کلاک: {clk:.0f} MHz" if clk is not None else "", "ok" if pw is not None else "na")

    # ---- خلاصه ----
    def set_summary(self, sm):
        self.lbl_meta.setText(f"شروع نشست {sm['started']}  |  مدت {sm['duration_s'] / 60:.1f} دقیقه  |  {sm['samples']} نمونه")

        t = self.tbl_sum
        t.setRowCount(len(self.ROWS))
        t.setFixedHeight(34 + 32 * len(self.ROWS) + 6)
        for r, key in enumerate(self.ROWS):
            label, unit = METRIC_INFO[key]
            a = sm["metrics"].get(key)
            vals = [f"{label} ({unit})"] + (
                [f"{a['min']:.1f}", f"{a['avg']:.1f}", f"{a['max']:.1f}", a["max_at"]] if a
                else ["—", "—", "—", "سنسور ندارد"])
            for c, v in enumerate(vals):
                t.setItem(r, c, self._item(v, c))

        t = self.tbl_stage
        stages = sm["stages"]
        t.setRowCount(len(stages))
        t.setFixedHeight(34 + 32 * max(1, len(stages)) + 6)
        for r, st in enumerate(stages):
            m = st["metrics"]
            vals = [st["label"] + (" ▶" if st["running"] else ""), f"{st['duration_s']:.0f}s",
                    _f(m["gpu_util"]["avg"], 0, "%") if "gpu_util" in m else "—",
                    _f(m["vram_pct"]["max"], 0, "%") if "vram_pct" in m else "—",
                    _f(m["gpu_temp"]["max"], 0, "°C") if "gpu_temp" in m else "—"]
            for c, v in enumerate(vals):
                t.setItem(r, c, self._item(v, c))
        self.lbl_warn.setText("\n".join("• " + w for w in sm["warnings"]) or "✓ مشکلی در این نشست ثبت نشد.")

    @staticmethod
    def _item(text, col):
        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignCenter if col else Qt.AlignRight | Qt.AlignVCenter)
        return it

    def clear(self):
        self.chart.clear()
