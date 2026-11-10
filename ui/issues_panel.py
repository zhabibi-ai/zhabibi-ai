"""پنل ایرادات: کارت‌های شماره‌دار با «برو به محل / حل شد / حذف»، فیلتر و شمارنده."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .icons import icon
from .styles import C

TYPE_COLORS = {
    "اختلاف": C.red, "تناقض": C.red, "ابهام": C.amber, "شک": C.amber,
    "نگارشی": C.purple, "افتادگی": C.gold, "بررسی": C.muted,
}
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(value) -> str:
    return str(value).translate(_FA)


def _clock(seconds) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _quote_text(rec) -> str:
    if rec["start"] and rec["end"]:
        return f"«{rec['start']}  …  {rec['end']}»"
    return f"«{rec['text'] or rec['start']}»"


class IssueCard(QFrame):
    locate = Signal(int)
    accept = Signal(int)
    resolve = Signal(int)
    restore = Signal(int)
    delete = Signal(int)

    def __init__(self, idx, rec):
        super().__init__()
        self.idx = idx
        self.setObjectName("IssueCard")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setAttribute(Qt.WA_StyledBackground, True)

        color = TYPE_COLORS.get(rec["type"], C.muted)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(7)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.num = QLabel(_fa(rec["number"]))
        self.num.setFixedSize(26, 26)
        self.num.setAlignment(Qt.AlignCenter)
        self.num.setStyleSheet(
            f"background:{C.card_alt}; color:{C.white}; border:1px solid {C.border};"
            "border-radius:13px; font-weight:700; font-size:11px;")
        head.addWidget(self.num)

        self.kind = QLabel(rec["type"])
        self.kind.setStyleSheet(
            f"color:{color}; border:1px solid {color}; border-radius:8px; padding:1px 9px;"
            "font-size:11px; font-weight:700;")
        head.addWidget(self.kind)

        if rec["time"] is not None:
            clock = QLabel(_clock(rec["time"]))
            clock.setLayoutDirection(Qt.LeftToRight)
            clock.setStyleSheet(f"color:{C.muted}; font-size:11px;")
            head.addWidget(clock)
        head.addStretch()
        self.state_lbl = QLabel("")
        head.addWidget(self.state_lbl)
        lay.addLayout(head)

        self.title = QLabel(_quote_text(rec))
        self.title.setWordWrap(True)
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.title)

        self.desc = QLabel(rec["desc"])
        self.desc.setWordWrap(True)
        self.desc.setVisible(bool(rec["desc"]))
        lay.addWidget(self.desc)

        self.fix = QLabel(f"پیشنهاد:  {rec['fix']}")
        self.fix.setWordWrap(True)
        self.fix.setVisible(bool(rec["fix"]))
        lay.addWidget(self.fix)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.btn_locate = self._button("برو به محل", "locate", "Secondary")
        self.btn_restore = self._button("بازگردانی", "refresh", "Secondary")
        self.btn_delete = self._button("", "trash", "Danger")
        self.btn_delete.setToolTip("حذف این مورد از لیست (ایراد اشتباه یا نامربوط)")
        row1.addWidget(self.btn_locate, 1)
        row1.addWidget(self.btn_restore, 1)
        row1.addWidget(self.btn_delete)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self.btn_accept = self._button("پذیرش و جایگزینی", "check", "Primary")
        self.btn_accept.setToolTip("عبارت پیشنهادی جایگزین عبارت داخل متن می‌شود (با «واگرد» قابل‌بازگشت است).")
        self.btn_resolve = self._button("حل شد", "check", "Secondary")
        row2.addWidget(self.btn_accept, 1)
        row2.addWidget(self.btn_resolve, 1)
        lay.addLayout(row2)

        self.btn_locate.clicked.connect(lambda *_: self.locate.emit(self.idx))
        self.btn_accept.clicked.connect(lambda *_: self.accept.emit(self.idx))
        self.btn_resolve.clicked.connect(lambda *_: self.resolve.emit(self.idx))
        self.btn_restore.clicked.connect(lambda *_: self.restore.emit(self.idx))
        self.btn_delete.clicked.connect(lambda *_: self.delete.emit(self.idx))
        self._rec_state = None

    @staticmethod
    def _button(text, icon_name, kind):
        b = QPushButton(text)
        b.setObjectName(kind)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(30)
        b.setIcon(icon(icon_name, C.red if kind == "Danger" else ("#FFFFFF" if kind == "Primary" else C.muted), 15, C.text))
        if kind == "Danger":
            b.setFixedWidth(40)
        return b

    def update_state(self, rec, selected=False):
        state = rec["state"]
        self._rec_state = state
        border = C.gold if selected else C.border
        dim = state in ("resolved",)
        self.setStyleSheet(
            f"#IssueCard{{background:{C.card_alt}; border:1px solid {border}; border-radius:12px;}}")
        self.title.setStyleSheet(
            f"color:{C.subtle if dim else C.text}; font-size:13px; font-weight:700;")
        self.desc.setStyleSheet(f"color:{C.subtle if dim else C.muted}; font-size:11.5px;")
        self.fix.setStyleSheet(f"color:{C.subtle if dim else C.gold}; font-size:11.5px;")

        resolved_text = ("✓ جایگزین شد" if rec.get("accepted")
                         else "✓ اصلاح شد" if rec.get("auto_resolved") else "✓ حل شد")
        labels = {
            "open": ("", C.muted),
            "resolved": (resolved_text, C.green),
            "missing": ("در متن پیدا نشد", C.amber),
        }
        text, col = labels.get(state, ("", C.muted))
        if state == "open" and rec.get("partial"):
            text, col = "فقط ابتدای بخش پیدا شد", C.amber
        self.state_lbl.setText(text)
        self.state_lbl.setStyleSheet(f"color:{col}; font-size:11px; font-weight:700;")

        has_fix_text = bool(rec["fix"])
        self.btn_locate.setVisible(state == "open")
        self.btn_accept.setVisible(state == "open" and has_fix_text)
        self.btn_resolve.setVisible(state in ("open", "missing"))
        self.btn_restore.setVisible(state == "resolved" and bool(rec["indices"]))
        self.btn_resolve.setText("بدون تغییر" if (state == "open" and has_fix_text)
                                 else "حل شد" if state == "open" else "نادیده بگیر")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._rec_state == "open":
            self.locate.emit(self.idx)
        super().mousePressEvent(event)


class IssuesPanel(QWidget):
    locate_requested = Signal(int)
    accept_requested = Signal(int)
    undo_requested = Signal()
    resolve_requested = Signal(int)
    restore_requested = Signal(int)
    delete_requested = Signal(int)

    FILTERS = [("open", "باز"), ("resolved", "حل‌شده"), ("missing", "پیدا نشد"), ("all", "همه")]

    def __init__(self):
        super().__init__()
        self._records = []
        self._cards = {}
        self._filter = "open"
        self._selected = -1

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(5)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.chips = {}
        for key, text in self.FILTERS:
            b = QPushButton(text)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setChecked(key == self._filter)
            b.clicked.connect(lambda _=False, k=key: self.set_filter(k))
            self.group.addButton(b)
            self.chips[key] = b
            row.addWidget(b)
        root.addLayout(row)

        self.nav_row = QHBoxLayout()
        self.btn_prev = QPushButton("◀  قبلی")
        self.btn_next = QPushButton("بعدی  ▶")
        for b, step in ((self.btn_prev, -1), (self.btn_next, 1)):
            b.setObjectName("Secondary")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, st=step: self.step(st))
            self.nav_row.addWidget(b, 1)
        self.btn_undo = QPushButton("↶ واگرد")
        self.btn_undo.setObjectName("Secondary")
        self.btn_undo.setCursor(Qt.PointingHandCursor)
        self.btn_undo.setToolTip("آخرین «پذیرش و جایگزینی» را برمی‌گرداند.")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(lambda *_: self.undo_requested.emit())
        self.nav_row.addWidget(self.btn_undo, 1)
        root.addLayout(self.nav_row)

        self.empty = QLabel("")
        self.empty.setObjectName("EmptyStateText")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setLayoutDirection(Qt.RightToLeft)
        root.addWidget(self.empty, 1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.inner.setObjectName("Panel")
        self.cards_layout = QVBoxLayout(self.inner)
        self.cards_layout.setContentsMargins(0, 0, 6, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.inner)
        root.addWidget(self.scroll, 1)
        self._update_empty()

    # ---- ساخت ----
    def set_records(self, records):
        for card in self._cards.values():
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        self._records = records
        self._selected = -1
        states = [r["state"] for r in records]
        for key in ("open", "missing", "resolved"):
            if key in states:
                self._filter = key
                self.chips[key].setChecked(True)
                break
        for idx, rec in enumerate(records):
            card = IssueCard(idx, rec)
            card.locate.connect(self.locate_requested.emit)
            card.accept.connect(self.accept_requested.emit)
            card.resolve.connect(self.resolve_requested.emit)
            card.restore.connect(self.restore_requested.emit)
            card.delete.connect(self.delete_requested.emit)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
            self._cards[idx] = card
        self.refresh()

    def refresh(self):
        counts = {"open": 0, "resolved": 0, "missing": 0}
        for idx, rec in enumerate(self._records):
            card = self._cards.get(idx)
            if rec["state"] == "deleted":
                if card:
                    card.setVisible(False)
                continue
            counts[rec["state"]] = counts.get(rec["state"], 0) + 1
            if card:
                card.update_state(rec, selected=(idx == self._selected))
                card.setVisible(self._filter_matches(rec))
        total = sum(counts.values())
        for key, text in self.FILTERS:
            n = total if key == "all" else counts.get(key, 0)
            self.chips[key].setText(f"{text} ({_fa(n)})")
        self._counts = counts
        self._update_empty()

    def counts(self):
        return getattr(self, "_counts", {"open": 0, "resolved": 0, "missing": 0})

    def _filter_matches(self, rec):
        if rec["state"] == "deleted":
            return False
        return self._filter == "all" or rec["state"] == self._filter

    def _update_empty(self):
        # قبلاً از isVisibleTo() استفاده می‌شد؛ چون خودِ لیست در شروع مخفی بود،
        # هیچ کارتی «قابل‌نمایش» حساب نمی‌شد و لیست برای همیشه مخفی می‌ماند.
        visible = any(self._filter_matches(r) for r in self._records)
        if not self._records:
            self.empty.setText(
                "هنوز لیست ایراداتی بارگذاری نشده.\n"
                "فایل بدهید یا متن را بچسبانید؛ با دکمه‌ی «قالب Gemini» می‌توانید قالب را کپی کنید.")
        elif not visible:
            self.empty.setText("موردی در این دسته نیست.")
        self.empty.setVisible(not visible)
        self.scroll.setVisible(visible)
        for b in (self.btn_prev, self.btn_next):
            b.setEnabled(bool(self._records))

    def set_undo_enabled(self, enabled: bool):
        self.btn_undo.setEnabled(bool(enabled))

    # ---- فیلتر و انتخاب ----
    def set_filter(self, key):
        self._filter = key
        self.chips[key].setChecked(True)
        self.refresh()

    def select(self, idx):
        self._selected = idx
        self.refresh()
        card = self._cards.get(idx)
        if card is not None and card.isVisibleTo(self):
            self.scroll.ensureWidgetVisible(card, 0, 40)

    def open_indices(self):
        return [i for i, r in enumerate(self._records) if r["state"] == "open" and r["indices"]]

    def step(self, direction):
        """رفتن به ایراد باز بعدی/قبلی (به ترتیب جایگاه در متن)."""
        order = sorted(self.open_indices(), key=lambda i: self._records[i]["indices"][0])
        if not order:
            return
        if self._filter != "open" and self._filter != "all":
            self.set_filter("open")
        cur = self._selected if self._selected in order else None
        if cur is None:
            target = order[0] if direction > 0 else order[-1]
        else:
            pos = order.index(cur) + direction
            target = order[pos % len(order)]
        self.locate_requested.emit(target)

    def next_open_after(self, idx):
        order = sorted(self.open_indices(), key=lambda i: self._records[i]["indices"][0])
        if not order:
            return None
        pos = -1
        if 0 <= idx < len(self._records) and self._records[idx]["indices"]:
            pos = self._records[idx]["indices"][0]
        after = [i for i in order if self._records[i]["indices"][0] > pos]
        return (after or order)[0]
