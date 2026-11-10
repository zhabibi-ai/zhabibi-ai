"""قالب ساده‌ی ایرادات (برای دادن به Gemini) + خواندن آن + پیدا کردن محل دقیق در متن.

قالب هر ایراد (بلاک‌ها با خط خالی جدا می‌شوند):

    ایراد 1
    نوع: ابهام
    زمان: 03:25
    متن: «عبارت دقیقاً کپی‌شده از متن»
    شرح: توضیح کوتاه
    پیشنهاد: اصلاح پیشنهادی

برای ایراد چندجمله‌ای به‌جای «متن» از «شروع» و «پایان» استفاده می‌شود؛ برنامه
از ابتدای «شروع» تا انتهای «پایان» را هایلایت می‌کند.
خواندن آن در برابر کپی/پیست مقاوم است: بولت، بولد، بک‌تیک، نقل‌قول‌های مختلف،
ارقام فارسی، کاراکترهای نامرئی RTL و ترتیب متفاوت خطوط پشتیبانی می‌شود.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from .alignment import ISSUE_THRESHOLD, normalize, parse_issues

ISSUE_TYPES = ["اختلاف", "ابهام", "نگارشی", "تناقض", "افتادگی", "سایر"]
MAX_SPAN_WORDS = 160

PROMPT = """تو یک ویراستار بسیار دقیق هستی. صوت و «متن اصلاح‌شده» را با هم مقایسه کن و «همه‌ی» مواردی را که باید دوباره با صوت بررسی شوند فهرست کن (واژه‌ی مشکوک، ابهام در نام، اختلاف با صوت، افتادگی). هیچ موردی را جا نینداز.

خروجی را فقط داخل «یک بلاک کد» بده؛ هر مورد یک خط، دقیقاً با این قالب:

شماره. «عبارت دقیق در متن اصلاح‌شده» | پیشنهاد: جایگزین احتمالی | وضعیت: توضیح کوتاه علت بررسی صوت

نمونه:
1. «در کنار مرقد آن مرد بزرگوار» | پیشنهاد: در کنار مغرب آن آدم بزرگوار | وضعیت: شک در تشخیص واژه (مرقد یا مغرب)
2. «غلامعلی صداقت‌نژاد» | پیشنهاد: غلامعلی معتمدی | وضعیت: ابهام در نام شخص

قوانین ثابت:
1) در هر خط فقط یک «...» بیاید و محتوای آن عیناً و کلمه‌به‌کلمه از متن اصلاح‌شده کپی شده باشد (بدون سه‌نقطه، بدون تغییر املا یا نیم‌فاصله). ۲ تا ۸ کلمه کافی است و ترجیحاً در متن یکتا باشد.
2) جداکننده‌ی سه بخش همیشه علامت | است.
3) «پیشنهاد:» عبارتی است که اگر کاربر دکمه‌ی «پذیرش» را بزند، دقیقاً جایگزین عبارت داخل « » می‌شود؛ پس باید املا و نگارش درست داشته باشد و مستقیم قابل‌جایگزینی باشد. اگر پیشنهادی نداری بنویس: پیشنهاد: —
4) «وضعیت:» توضیح کوتاه و یک‌خطی از علت بررسی صوت.
5) موارد را به ترتیب وقوع در متن شماره‌گذاری کن، بین مورد‌ها خط خالی نگذار و هیچ توضیح اضافه‌ای ننویس.
"""

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_INVISIBLE = dict.fromkeys(map(ord, "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff\u00a0"), " ")
_QUOTES = "«»\"“”„‟'‘’‹›`"

KEY_ALIASES = {
    "type": ["نوع", "دسته", "type", "kind"],
    "time": ["زمان", "time", "لحظه"],
    "text": ["متن", "عبارت", "text", "phrase"],
    "start": ["شروع", "ابتدا", "از", "start", "from"],
    "end": ["پایان", "انتها", "تا", "end", "to"],
    "desc": ["شرح", "توضیح", "توضیحات", "مشکل", "desc", "description", "note"],
    "fix": ["پیشنهاد", "اصلاح", "جایگزین", "fix", "suggestion"],
}
_KEY_LOOKUP = {alias: canon for canon, names in KEY_ALIASES.items() for alias in names}
_HEADER = re.compile(
    r"^(?:ایراد|مورد|issue|#)?\s*#?\s*[\[\(]?\s*(\d{1,4})\s*[\]\)]?\s*[\.\):\-–]*\s*$", re.I)
_KEYLINE = re.compile(r"^([^:：\n]{1,14}?)\s*[:：]\s*(.*)$")
_TIME = re.compile(r"(\d{1,3}):(\d{2})(?::(\d{2}))?")


def _clean_line(line: str) -> str:
    line = line.translate(_INVISIBLE)
    line = line.replace("**", "").replace("__", "").replace("`", "")
    line = re.sub(r"^[\s>*\-•●▪·#]+(?=\S)", "", line.strip()) if not _HEADER.match(line.strip().translate(_DIGITS)) else line.strip()
    return line.strip()


def _unquote(value: str) -> str:
    value = value.strip()
    for left, right in (("«", "»"), ("“", "”"), ("”", "“"), ('"', '"')):
        a, b = value.find(left), value.rfind(right)
        if a != -1 and b > a:
            return value[a + 1:b].strip()
    return value.strip(_QUOTES + " ")


def _parse_time(value: str):
    m = _TIME.search(value.translate(_DIGITS))
    if not m:
        return None
    a, b, c = int(m.group(1)), int(m.group(2)), m.group(3)
    return a * 3600 + b * 60 + int(c) if c is not None else a * 60 + b


def _is_key_line(line: str):
    m = _KEYLINE.match(line)
    if not m:
        return None
    canon = _KEY_LOOKUP.get(m.group(1).strip("*_ ").lower())
    return (canon, m.group(2).strip()) if canon else None


_NUMBER_PREFIX = re.compile(r"^([0-9۰-۹٠-٩]{1,4})\s*[\.\)\-:–]\s*(.*)$")
_QUOTED = re.compile(r"[«“\"]([^»”\"]+)[»”\"]")
_PIPES = re.compile(r"[｜¦│∣ǀ]")
_NO_FIX = {"", "-", "—", "–", "ندارد", "بدون پیشنهاد", "نامشخص"}
_FIX_KEYS = ("پیشنهاد", "اصلاح", "جایگزین", "جایگزینی", "suggestion", "fix")
_DESC_KEYS = ("وضعیت", "توضیح", "شرح", "علت", "status", "note")
_KIND_WORDS = [("ابهام", "ابهام"), ("شک", "شک"), ("اختلاف", "اختلاف"), ("افتادگی", "افتادگی"),
               ("نگارش", "نگارشی"), ("تناقض", "تناقض")]


def has_fix(fix: str) -> bool:
    return fix.strip().strip("—–-").strip() not in _NO_FIX and fix.strip() not in _NO_FIX


def _line_clean(raw: str) -> str:
    line = raw.translate(_INVISIBLE).replace("**", "").replace("__", "").replace("`", "")
    line = _PIPES.sub("|", line).strip()
    return re.sub(r"^[\s>*•●▪·]+(?=\S)", "", line).strip()


def looks_like_line_format(text: str) -> bool:
    for raw in str(text or "").splitlines():
        line = _line_clean(raw)
        if "|" in line and _QUOTED.search(line) and any(k in line for k in _FIX_KEYS + _DESC_KEYS):
            return True
    return False


def _split_fields(rest: str):
    fix, desc = "", []
    for part in rest.split("|"):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([^:：]{1,14}?)\s*[:：]\s*(.*)$", part)
        key = m.group(1).strip().lower() if m else ""
        if m and key in _FIX_KEYS:
            fix = m.group(2).strip()
        elif m and key in _DESC_KEYS:
            desc.append(m.group(2).strip())
        elif part not in ("→", "←", "=>"):
            desc.append(part)
    return fix, " ".join(d for d in desc if d)


def _kind_of(desc: str) -> str:
    for word, kind in _KIND_WORDS:
        if word in desc:
            return kind
    return "بررسی"


def parse_line_format(text: str) -> list[dict]:
    """«عبارت» | پیشنهاد: ... | وضعیت: ...  — هر خط یک ایراد (خطوط ادامه به قبلی می‌چسبند)."""
    items = []
    for line_no, raw in enumerate(str(text or "").splitlines(), 1):
        line = _line_clean(raw)
        if not line or line.startswith("```") or line.lower() in ("plaintext", "text", "txt"):
            continue
        number, body = None, line
        m = _NUMBER_PREFIX.match(line)
        if m:
            number, body = int(m.group(1).translate(_DIGITS)), m.group(2)
        q = _QUOTED.search(body)
        if q:
            items.append({"number": number, "phrase": q.group(1).strip(), "rest": body[q.end():], "line": line_no})
        elif items:
            items[-1]["rest"] += " " + line
    out = []
    for n, it in enumerate(items, 1):
        fix, desc = _split_fields(it["rest"])
        out.append(_record(it["number"] or n, _kind_of(desc), None, it["phrase"], "", "", desc,
                           "" if not has_fix(fix) else fix, it["line"]))
    return out


def looks_like_new_format(text: str) -> bool:
    for raw in str(text or "").splitlines():
        hit = _is_key_line(_clean_line(raw))
        if hit and hit[0] in ("type", "text", "start", "end"):
            return True
    return False


def parse_issue_blocks(text: str) -> list[dict]:
    """متن لیست ایرادات → فهرست رکورد. اگر قالب جدید نبود، قالب قدیمی (« » و [ ]) خوانده می‌شود."""
    text = str(text or "")
    if not text.strip():
        return []
    if looks_like_line_format(text):
        return parse_line_format(text)
    if not looks_like_new_format(text):
        out = []
        for n, item in enumerate(parse_issues(text), 1):
            fix = "" if item["suggestion"] == "نیاز به بررسی" else item["suggestion"]
            out.append(_record(n, "سایر", None, item["target"], "", "", "", fix, item["line"]))
        return out

    blocks, cur, last_key = [], None, None

    def new_block(number, line_no):
        nonlocal cur, last_key
        cur = {"number": number, "line": line_no, "fields": {}}
        blocks.append(cur)
        last_key = None

    for line_no, raw in enumerate(text.splitlines(), 1):
        line = _clean_line(raw)
        if not line or set(line) <= set("-=_*~—– "):
            continue
        header = _HEADER.match(line.translate(_DIGITS))
        if header:
            new_block(int(header.group(1)), line_no)
            continue
        hit = _is_key_line(line)
        if hit:
            key, value = hit
            if cur is None or (key == "type" and "type" in cur["fields"]):
                new_block(None, line_no)
            cur["fields"][key] = value
            last_key = key
        elif cur is not None and last_key in ("desc", "fix", "text", "start", "end"):
            cur["fields"][last_key] = (cur["fields"][last_key] + " " + line).strip()

    out = []
    for n, b in enumerate(blocks, 1):
        f = b["fields"]
        out.append(_record(
            b["number"] or n, f.get("type", "").strip() or "سایر", _parse_time(f.get("time", "")),
            _unquote(f.get("text", "")), _unquote(f.get("start", "")), _unquote(f.get("end", "")),
            f.get("desc", "").strip(), f.get("fix", "").strip(), b["line"]))
    return out


def _record(number, kind, time_s, text, start, end, desc, fix, line):
    return {"number": number, "type": kind, "time": time_s, "text": text, "start": start, "end": end,
            "desc": desc, "fix": fix, "line": line,
            "state": "missing", "indices": [], "partial": False, "auto_resolved": False, "accepted": False,
            "key": f"{number}|{normalize(text or start)[:40]}"}


# ==========================================
# پیدا کردن محل دقیق
# ==========================================
def _find_exact(clean, pw, lo=0, hi=None):
    n = len(pw)
    if n == 0:
        return []
    last = len(clean) - n if hi is None else min(hi, len(clean) - n)
    return [i for i in range(max(0, lo), last + 1) if clean[i] == pw[0] and clean[i:i + n] == pw]


def _find_fuzzy(clean, pw, lo=0, hi=None, threshold=ISSUE_THRESHOLD):
    n = len(pw)
    if n == 0:
        return None
    target = " ".join(pw)
    best = (0.0, -1, n)
    for length in sorted({max(1, n - 1), n, n + 1}):
        last = len(clean) - length if hi is None else min(hi, len(clean) - length)
        for k in range(max(0, lo), last + 1):
            if fuzz.ratio(pw[0], clean[k]) < 60 and fuzz.ratio(pw[-1], clean[k + length - 1]) < 60:
                continue
            score = fuzz.ratio(target, " ".join(clean[k:k + length]))
            if score > best[0]:
                best = (score, k, length)
    return (best[1], best[2]) if best[0] >= threshold else None


def _find_phrase(clean, phrase, lo=0, hi=None, fuzzy=True):
    """[(start, length)] — اول تطبیق دقیق، وگرنه (در صورت اجازه) بهترین تطبیق فازی."""
    pw = normalize(phrase).split()
    exact = _find_exact(clean, pw, lo, hi)
    if exact:
        return [(i, len(pw)) for i in exact]
    found = _find_fuzzy(clean, pw, lo, hi) if fuzzy else None
    return [found] if found else []


def _order(cands, starts, time_hint, cursor, claimed):
    free = [c for c in cands if c[0] not in claimed] or cands
    if time_hint is not None and starts:
        return sorted(free, key=lambda c: abs(starts[c[0]] - time_hint))
    return sorted(free, key=lambda c: (c[0] < cursor, c[0]))


def locate_records(words, records, other_words=None):
    """words: کلمات زمان‌دار متن نمایش‌داده‌شده | other_words: کلمات متن دیگر (برای تشخیص «اصلاح‌شده»)."""
    clean = [normalize(w["word"]) for w in words]
    starts = [w["start"] for w in words]
    other = [normalize(w) for w in other_words] if other_words else None
    claimed, cursor = set(), 0

    def fuzzy_ok(phrase):
        # اگر عبارت عیناً در متن دیگر (خام) هست ولی در متن نمایش‌داده‌شده نیست، یعنی اصلاح شده؛
        # پس تطبیق تقریبی نباید آن را «هنوز موجود» نشان دهد.
        if other is None or not phrase:
            return True
        return not _find_exact(other, normalize(phrase).split())

    for rec in records:
        rec.update(state="missing", indices=[], partial=False, auto_resolved=False, accepted=False)
        span = None
        if rec["start"]:
            for s, ln in _order(_find_phrase(clean, rec["start"], fuzzy=fuzzy_ok(rec["start"])),
                                starts, rec["time"], cursor, claimed):
                if rec["end"]:
                    ends = _find_phrase(clean, rec["end"], lo=s, hi=s + MAX_SPAN_WORDS)
                    ends = [e for e in ends if e[0] + e[1] - 1 >= s]
                    if ends:
                        e0, el = min(ends, key=lambda e: e[0])
                        span = (s, e0 + el - 1)
                        break
                if span is None:
                    span = (s, s + ln - 1)
                    rec["partial"] = bool(rec["end"])
                    if not rec["end"]:
                        break
        if span is None and rec["text"]:
            cands = _order(_find_phrase(clean, rec["text"], fuzzy=fuzzy_ok(rec["text"])),
                           starts, rec["time"], cursor, claimed)
            if cands:
                s, ln = cands[0]
                span = (s, s + ln - 1)

        if span:
            claimed.add(span[0])
            cursor = span[0]
            rec.update(state="open", indices=list(range(span[0], span[1] + 1)))
        elif other is not None:
            probe = rec["text"] or rec["start"]
            if probe and _find_phrase(other, probe):
                rec.update(state="resolved", auto_resolved=True)
    return records
