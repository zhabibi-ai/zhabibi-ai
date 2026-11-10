"""منطق خالص (بدون Qt) برای نرمال‌سازی، تراز زمانی، ایرادات و بخش‌بندی.

همه‌ی توابع این فایل مستقل از رابط کاربری هستند تا بتوان آن‌ها را جداگانه تست کرد.
"""
from __future__ import annotations

import bisect
import re

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

MANUAL_DURATION = 0.35        # طول پیش‌فرض یک کلمه‌ی لنگر دستی (ثانیه)
MAX_SEC_PER_CHAR = 0.08       # سقف کشیدگی کلمات تخمینی
ISSUE_THRESHOLD = 80          # آستانه‌ی تطبیق فازی ایرادات

_CHAR_MAP = str.maketrans({
    "ي": "ی", "ك": "ک", "ؤ": "و", "أ": "ا", "إ": "ا", "آ": "ا",
    "ة": "ه", "ۀ": "ه", "\u200c": "",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})
_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u0640]")
_PUNCT = re.compile(r"[^\w\s]")


def normalize(text) -> str:
    """نرمال‌سازی عمیق فارسی برای مقایسه‌ی کلمات."""
    text = str(text).translate(_CHAR_MAP)
    text = _DIACRITICS.sub("", text)
    text = _PUNCT.sub("", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def split_words(text: str):
    """متن را به کلمات می‌شکند و مشخص می‌کند هر خط (پاراگراف) کجا تمام می‌شود."""
    words, para_end = [], set()
    for line in str(text).splitlines():
        parts = [w for w in re.split(r"\s+", line.strip()) if w]
        if not parts:
            continue
        words.extend(parts)
        para_end.add(len(words) - 1)
    return words, para_end


# ==========================================
# تراز زمانی
# ==========================================
def _lis(indices, key):
    """طولانی‌ترین زیردنباله‌ی غیرنزولی (برای حذف لنگرهای ناسازگار)."""
    tails, tail_vals = [], []
    prev = [-1] * len(indices)
    for p, i in enumerate(indices):
        v = key(i)
        pos = bisect.bisect_right(tail_vals, v)
        if pos > 0:
            prev[p] = tails[pos - 1]
        if pos == len(tails):
            tails.append(p)
            tail_vals.append(v)
        else:
            tails[pos] = p
            tail_vals[pos] = v
    out = []
    p = tails[-1] if tails else -1
    while p != -1:
        out.append(indices[p])
        p = prev[p]
    return out[::-1]


def rebuild_times(words: list) -> None:
    """زمان همه‌ی کلمات را از روی لنگرها دوباره می‌سازد (درجا).

    ترتیب اولویت: لنگر دستی  >  لنگر Whisper (فقط اگر با ترتیب متن و لنگرهای دستی سازگار باشد)
    >  میان‌یابی تناسبی. خروجی همیشه با ترتیب کلمات «غیرنزولی» است، پس پرش بالا/پایین ندارد.
    """
    n = len(words)
    if not n:
        return
    inf = float("inf")

    lower, cur = [0.0] * n, 0.0
    for i, w in enumerate(words):
        if w.get("manual"):
            cur = w["manual_start"]
        lower[i] = cur
    upper, cur = [inf] * n, inf
    for i in range(n - 1, -1, -1):
        if words[i].get("manual"):
            cur = words[i]["manual_start"]
        upper[i] = cur

    cand = [
        i for i, w in enumerate(words)
        if not w.get("manual") and w.get("asr_start") is not None
        and lower[i] - 1e-6 <= w["asr_start"] <= upper[i] + 1e-6
    ]
    keep = set(_lis(cand, key=lambda i: words[i]["asr_start"]))

    for i, w in enumerate(words):
        if w.get("manual"):
            w["start"], w["end"], w["estimated"] = w["manual_start"], w["manual_end"], False
        elif i in keep:
            w["start"] = w["asr_start"]
            w["end"] = max(w["asr_end"], w["asr_start"])
            w["estimated"] = False
        else:
            w["start"] = w["end"] = None
            w["estimated"] = True

    i, prev_end = 0, 0.0
    while i < n:
        if words[i]["start"] is not None:
            prev_end = words[i]["end"]
            i += 1
            continue
        j = i
        while j < n and words[j]["start"] is None:
            j += 1
        lengths = [max(1, len(words[k]["word"])) for k in range(i, j)]
        total = sum(lengths)
        gap = max(0.0, words[j]["start"] - prev_end) if j < n else total * MAX_SEC_PER_CHAR
        t = prev_end
        for k, length in zip(range(i, j), lengths):
            dur = min(gap * length / total, length * MAX_SEC_PER_CHAR)
            words[k]["start"], words[k]["end"] = t, t + dur
            t += dur
        prev_end = words[j - 1]["end"]
        i = j

    last = 0.0
    for w in words:
        if w["start"] < last:
            w["start"] = last
            w["end"] = max(w["end"], last)
        last = w["start"]


def align_words(raw_words, asr_words, manual=None, para_end=None):
    """کلمات متن خام را با کلمات زمان‌دار Whisper تراز می‌کند."""
    para_end = para_end or set()
    timed = [{
        "word": w, "start": None, "end": None,
        "asr_start": None, "asr_end": None,
        "issue_data": None, "estimated": True, "manual": False,
        "para_end": i in para_end,
    } for i, w in enumerate(raw_words)]

    if asr_words and raw_words:
        raw_clean = [normalize(w) for w in raw_words]
        asr_clean = [normalize(w["word"]) for w in asr_words]
        for op in Levenshtein.opcodes(asr_clean, raw_clean):
            a1, a2, r1, r2 = op.src_start, op.src_end, op.dest_start, op.dest_end
            if op.tag == "equal" or (op.tag == "replace" and a2 - a1 == r2 - r1):
                for a, r in zip(range(a1, a2), range(r1, r2)):
                    if op.tag == "replace" and fuzz.ratio(asr_clean[a], raw_clean[r]) < 45:
                        continue
                    timed[r]["asr_start"] = float(asr_words[a]["start"])
                    timed[r]["asr_end"] = float(asr_words[a]["end"])

    for idx, t in (manual or {}).items():
        if 0 <= idx < len(timed):
            timed[idx].update(manual=True, manual_start=float(t),
                              manual_end=float(t) + MANUAL_DURATION)
    rebuild_times(timed)
    return timed


def set_manual_anchor(words, idx, t):
    words[idx].update(manual=True, manual_start=float(t),
                      manual_end=float(t) + MANUAL_DURATION)
    rebuild_times(words)


def clear_manual_anchor(words, idx):
    words[idx]["manual"] = False
    rebuild_times(words)


# ==========================================
# لیست ایرادات
# ==========================================
_BULLET = re.compile(r"^\s*(?:[-•*●▪]|\d+\s*[\.\)\-:])\s*")
_QUOTES = [
    re.compile(r"«([^»]+)»"),
    re.compile(r"“([^”]+)”"),
    re.compile(r"”([^“]+)“"),
    re.compile(r'"([^"]+)"'),
]


def parse_issues(text: str):
    issues = []
    for number, line in enumerate(str(text or "").splitlines(), 1):
        line = _BULLET.sub("", line.strip())
        if not line:
            continue
        brackets = re.findall(r"\[(.*?)\]", line)
        suggestion = brackets[0].strip() if brackets else ""
        scan = re.sub(r"\[.*?\]", " ", line)

        targets = []
        for pattern in _QUOTES:
            targets = [t.strip() for t in pattern.findall(scan) if t.strip()]
            if targets:
                break
        for target in targets:
            if len(target) > 1:
                issues.append({"line": number, "target": target,
                               "suggestion": suggestion or "نیاز به بررسی"})
    return issues


def locate_issues(raw_words, issues, threshold=ISSUE_THRESHOLD):
    """هر ایراد را در متن پیدا می‌کند. خروجی: (پیدا‌شده‌ها، پیدا‌نشده‌ها)."""
    clean = [normalize(w) for w in raw_words]
    joined = " ".join(clean)
    starts, pos = [], 0
    for c in clean:
        starts.append(pos)
        pos += len(c) + 1

    claimed, found, missing = set(), [], []
    for issue in issues:
        target = normalize(issue["target"])
        t_words = target.split()
        if not t_words:
            missing.append(issue)
            continue

        best_idx, best_len, best_score = -1, len(t_words), 0.0
        # ۱) تطبیق دقیق؛ اگر چند بار آمده، اولین مورد آزاد
        at = joined.find(target)
        while at != -1:
            before_ok = at == 0 or joined[at - 1] == " "
            end = at + len(target)
            after_ok = end == len(joined) or joined[end] == " "
            if before_ok and after_ok:
                k = bisect.bisect_right(starts, at) - 1
                if k not in claimed:
                    best_idx, best_score = k, 100.0
                    break
            at = joined.find(target, at + 1)

        # ۲) تطبیق فازی با پنجره‌های هم‌طول و ±۱
        if best_idx < 0:
            for length in sorted({max(1, len(t_words) - 1), len(t_words), len(t_words) + 1}):
                for k in range(0, len(clean) - length + 1):
                    if k in claimed:
                        continue
                    score = fuzz.ratio(target, " ".join(clean[k:k + length]))
                    if score > best_score:
                        best_idx, best_len, best_score = k, length, score

        if best_idx >= 0 and best_score >= threshold:
            claimed.add(best_idx)
            found.append({**issue, "indices": list(range(best_idx, best_idx + best_len)),
                          "score": best_score})
        else:
            missing.append(issue)
    return found, missing


# ==========================================
# مقایسه با متن اصلاح‌شده و بخش‌بندی
# ==========================================
def diff_statuses(raw_words, corrected_text):
    """وضعیت هر کلمه‌ی متن خام نسبت به متن اصلاح‌شده: changed / added."""
    corrected = [normalize(w) for w in str(corrected_text).split()]
    raw = [normalize(w) for w in raw_words]
    result = {}
    if not corrected or not raw:
        return result
    for op in Levenshtein.opcodes(raw, corrected):
        if op.tag in ("replace", "delete"):
            for i in range(op.src_start, op.src_end):
                result[i] = "changed"
        elif op.tag == "insert":
            i = op.src_start - 1 if op.src_start > 0 else 0
            if 0 <= i < len(raw):
                result.setdefault(i, "added")
    return result


def build_segments(words, max_words=30):
    segments, current = [], []

    def flush():
        if not current:
            return
        a, b = current[0], current[-1]
        segments.append({
            "index": len(segments) + 1, "first": a, "last": b,
            "start": float(words[a]["start"] or 0.0),
            "end": float(words[b]["end"] or words[a]["start"] or 0.0),
            "text": " ".join(words[i]["word"] for i in current),
            "status": "confirmed",
        })
        current.clear()

    for i, w in enumerate(words):
        current.append(i)
        tail = w["word"].rstrip("»”\")'’)")
        if tail.endswith((".", "؟", "!", "?", "…")) or w.get("para_end") or len(current) >= max_words:
            flush()
    flush()
    return segments


_PRIORITY = ["changed", "added", "needs_review", "guessed", "confirmed"]


def segment_status(statuses):
    present = set(statuses)
    for key in _PRIORITY[:3]:
        if key in present:
            return key
    guessed = sum(1 for s in statuses if s == "guessed")
    return "guessed" if statuses and guessed / len(statuses) > 0.5 else "confirmed"


def paragraphs_from_text(text: str):
    """متن ساده → پاراگراف‌هایی از (کلمه، وضعیت) برای نمایش ادیتور."""
    words, para_end = split_words(text)
    use_lines = len(para_end) >= 2
    paragraphs, current = [], []
    for i, w in enumerate(words):
        current.append((w, "confirmed"))
        end = (i in para_end) if use_lines else w.endswith((".", "؟", "!"))
        if end:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return paragraphs
