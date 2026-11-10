# ==============================================================================
# موتور پردازش صوت و همگام‌سازی متن (Faster-Whisper + Alignment)
# ==============================================================================
import gc
import os
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

from PySide6.QtCore import QThread, Signal

from .alignment import align_words, split_words
from .issue_format import locate_records, parse_issue_blocks

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# ==========================================
# مدل‌های همراه برنامه (کار آفلاین)
# ==========================================
def app_base_dir() -> str:
    """پوشه‌ی برنامه: در حالت exe همان _internal، در حالت اسکریپت ریشه‌ی پروژه."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def model_search_dirs():
    dirs = [os.path.join(app_base_dir(), "models")]
    if getattr(sys, "frozen", False):
        dirs.insert(0, os.path.join(os.path.dirname(sys.executable), "models"))
    return [d for d in dirs if os.path.isdir(d)]


def resolve_model(name: str) -> str:
    """اگر مدل کنار برنامه باشد مسیر محلی‌اش را می‌دهد، وگرنه نام را برای دانلود برمی‌گرداند."""
    for base in model_search_dirs():
        path = os.path.join(base, name)
        if os.path.isfile(os.path.join(path, "model.bin")):
            return path
    return name


def is_model_local(name: str) -> bool:
    return resolve_model(name) != name


# ==========================================
# استخراج متن از فایل‌ها
# ==========================================
def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        lines = []
        with zipfile.ZipFile(file_path) as docx:
            tree = ET.XML(docx.read("word/document.xml"))
            for p in tree.iter(f"{_W}p"):
                texts = [n.text for n in p.iter(f"{_W}t") if n.text]
                if texts:
                    lines.append("".join(texts))
        return "\n".join(lines)

    raw = open(file_path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1256"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", errors="replace")


# ==========================================
# انتخاب دستگاه: GPU در اولویت، CPU به‌عنوان جایگزین
# ==========================================
def detect_cuda() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        pass
    mod = sys.modules.get("torch")
    try:
        if mod is None:
            import torch as mod
        return bool(mod.cuda.is_available())
    except Exception:
        return False


def pick_compute(device: str, wanted: str) -> str:
    try:
        import ctranslate2
        supported = set(ctranslate2.get_supported_compute_types(device))
    except Exception:
        supported = set()

    if wanted and wanted != "auto":
        ok = wanted in supported if supported else not (device == "cpu" and wanted.startswith("float16"))
        if ok:
            return wanted
    order = ["float16", "int8_float16", "int8"] if device == "cuda" else ["int8", "int8_float32", "float32"]
    for c in order:
        if not supported or c in supported:
            return c
    return "float16" if device == "cuda" else "int8"


def plan_devices(preference: str, wanted_compute: str):
    """فهرست (device, compute) به ترتیب تلاش. GPU اول؛ در صورت خطا یا نبودن، CPU."""
    pref = (preference or "auto").lower()
    has_cuda = detect_cuda()
    plan = []
    if pref in ("auto", "cuda") and has_cuda:
        plan.append(("cuda", pick_compute("cuda", wanted_compute)))
    plan.append(("cpu", pick_compute("cpu", wanted_compute if pref == "cpu" else "auto")))
    return plan, has_cuda


class _Cancelled(Exception):
    pass


# ==========================================
# تشخیص گفتار
# ==========================================
class AudioProcessorThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    timer_update = Signal(str)
    result_ready = Signal(object, float)
    error = Signal(str)
    log = Signal(str, str)        # (پیام، سطح)
    device_info = Signal(str)

    def __init__(self, audio_path, settings_dict):
        super().__init__()
        self.audio_path = audio_path
        self.settings = settings_dict
        self.is_cancelled = False
        self.start_time = 0.0

    def cancel(self):
        self.is_cancelled = True
        self.blockSignals(True)

    @staticmethod
    def format_time(seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _check(self):
        if self.is_cancelled:
            raise _Cancelled()

    def _transcribe(self, device, compute):
        from faster_whisper import WhisperModel

        cfg = self.settings
        label = "GPU" if device == "cuda" else "CPU"
        self.status.emit(f"بارگذاری مدل {cfg['model']} روی {label}...")
        self.log.emit(f"مدل {cfg['model']} | دستگاه: {device} | محاسبه: {compute}", "info")
        self.progress.emit(10)
        model_ref = resolve_model(cfg["model"])
        if model_ref == cfg["model"]:
            self.log.emit(f"مدل {cfg['model']} همراه برنامه نیست؛ تلاش برای دانلود (نیاز به اینترنت)...", "warn")
        try:
            model = WhisperModel(model_ref, device=device, compute_type=compute,
                                 cpu_threads=os.cpu_count() or 4)
        except Exception as exc:
            if model_ref == cfg["model"] and device == "cpu":
                raise RuntimeError(
                    f"مدل «{cfg['model']}» روی این سیستم موجود نیست و دانلود هم ممکن نشد. "
                    "یکی از مدل‌های همراه برنامه را انتخاب کنید یا به اینترنت وصل شوید.") from exc
            raise
        try:
            self._check()
            self.device_info.emit(f"{label} · {compute}")
            self.status.emit(f"پردازش صوت روی {label}...")
            self.progress.emit(25)

            lang = cfg["language"] if cfg["language"] != "auto" else None
            segments, info = model.transcribe(
                self.audio_path, language=lang, word_timestamps=True, beam_size=5,
                vad_filter=cfg["vad_filter"],
                condition_on_previous_text=cfg["condition_on_previous_text"],
            )
            duration = float(getattr(info, "duration", 0.0) or 0.0)

            words = []
            for seg in segments:
                self._check()
                for w in (seg.words or []):
                    words.append({"word": w.word.strip(), "start": float(w.start), "end": float(w.end)})
                if duration > 0:
                    self.progress.emit(25 + int(70 * min(1.0, seg.end / duration)))
                self.timer_update.emit(self.format_time(time.time() - self.start_time))
            return words
        finally:
            del model
            gc.collect()
            torch = sys.modules.get("torch")
            try:
                if torch is not None and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def run(self):
        try:
            self.start_time = time.time()
            plan, has_cuda = plan_devices(self.settings["device"], self.settings["compute_type"])
            if self.settings["device"] == "cuda" and not has_cuda:
                self.log.emit("کارت گرافیک NVIDIA (CUDA) پیدا نشد؛ پردازش روی CPU انجام می‌شود.", "warn")
            elif self.settings["device"] == "auto" and not has_cuda:
                self.log.emit("GPU در دسترس نیست؛ از CPU استفاده می‌شود.", "info")

            words = None
            for k, (device, compute) in enumerate(plan):
                try:
                    words = self._transcribe(device, compute)
                    break
                except _Cancelled:
                    return
                except Exception as exc:
                    if device == "cuda" and k + 1 < len(plan):
                        self.log.emit(f"اجرا روی GPU ناموفق بود ({exc}). تلاش دوباره روی CPU...", "warn")
                        continue
                    raise

            if self.is_cancelled or words is None:
                return
            total = time.time() - self.start_time
            self.progress.emit(100)
            self.timer_update.emit(self.format_time(total))
            self.status.emit("پردازش صوت با موفقیت پایان یافت.")
            self.result_ready.emit(words, total)
        except _Cancelled:
            return
        except Exception as exc:
            if not self.is_cancelled:
                self.error.emit(f"خطای پردازش: {exc}")


# ==========================================
# همگام‌سازی متن با زمان‌های صوت + پیدا کردن ایرادات
# ==========================================
class TextSyncThread(QThread):
    timer_update = Signal(str)
    result_ready = Signal(object, object, float)   # کلمات زمان‌دار، رکوردهای ایراد، زمان
    error = Signal(str)

    def __init__(self, main_text, issues_text, asr_words, manual_anchors=None, other_text=""):
        super().__init__()
        self.main_text = main_text
        self.issues_text = issues_text
        self.other_text = other_text
        self.asr_words = asr_words or []
        self.manual_anchors = dict(manual_anchors or {})

    def run(self):
        try:
            t0 = time.time()
            if self.main_text.strip():
                words, para_end = split_words(self.main_text)
            else:
                words, para_end = [w["word"] for w in self.asr_words], set()

            timed = align_words(words, self.asr_words, self.manual_anchors, para_end)

            records = parse_issue_blocks(self.issues_text)
            if records:
                other = split_words(self.other_text)[0] if self.other_text.strip() else None
                locate_records(timed, records, other)

            total = time.time() - t0
            self.timer_update.emit(f"{total:.1f}s")
            self.result_ready.emit(timed, records, total)
        except Exception as exc:
            self.error.emit(f"خطای همگام‌سازی: {exc}")
