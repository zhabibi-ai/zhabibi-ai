import bisect
import os
import re
import sys
import time
from pathlib import Path

# در حالت exe بدون کنسول، stdout/stderr وجود ندارد و برخی کتابخانه‌ها (tqdm, hf) با آن خطا می‌دهند.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _register_cuda_dlls():
    """DLLهای CUDA/cuDNN که داخل برنامه بسته‌بندی شده‌اند را برای ctranslate2 قابل‌پیدا می‌کند."""
    base = _base_dir()
    for sub in (base / "nvidia").glob("*/bin") if (base / "nvidia").is_dir() else []:
        try:
            os.add_dll_directory(str(sub))
        except (AttributeError, OSError):
            pass
        os.environ["PATH"] = str(sub) + os.pathsep + os.environ.get("PATH", "")


_register_cuda_dlls()

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from core.alignment import clear_manual_anchor, paragraphs_from_text, rebuild_times, set_manual_anchor
from core.issue_format import has_fix, parse_issue_blocks
from core.audio import WaveformThread
from core.hardware import HardwareMonitor, SessionRecorder, level_for_temp
from core.whisper import AudioProcessorThread, TextSyncThread, extract_text_from_file
from ui.main_window import MainWindow
from ui.styles import FONT_FAMILY, build_qss
from ui.widgets import MOD_ALT, MOD_CTRL

ROOT = _base_dir()


def load_fonts():
    for f in (ROOT / "assets" / "fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


def clock(seconds):
    m, s = divmod(max(0.0, seconds), 60)
    return f"{int(m):02d}:{s:04.1f}"


class AppController(QObject):
    def __init__(self, window):
        super().__init__()
        self.win = window

        # ---- ورودی‌ها ----
        self.audio_path = None
        self.raw_text = ""
        self.corrected_text = ""
        self.issues_text = ""
        self.cached_asr_words = None

        # ---- نتیجه ----
        self.words = []
        self.starts = []
        self.statuses = []
        self.issues = []              # رکوردهای ایراد؛ حذف‌شده‌ها state="deleted" می‌گیرند
        self.overrides = {}           # key ایراد -> "resolved" | "deleted" (برای حفظ تصمیم کاربر هنگام تطبیق مجدد)
        self.manual_anchors = {}
        self._text_key = None
        self.current_word = -1
        self.follow = False

        # ---- نخ‌ها ----
        self.audio_worker = None
        self.text_worker = None
        self.wave_worker = None
        self.hw_monitor = None
        self._zombies = []
        self._pending_resync = False
        self._accept_history = []     # برای واگرد «پذیرش و جایگزینی»

        self.recorder = SessionRecorder()
        self._tick = 0

        # ---- پلیر ----
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(self.win.volume.value() / 100.0)
        self.player.setAudioOutput(self.audio_output)

        self.follower_timer = QTimer()
        self.follower_timer.setInterval(50)
        self.follower_timer.timeout.connect(self.update_player_ui)

        self.player.positionChanged.connect(lambda _=0: self.update_player_ui())
        self.player.durationChanged.connect(lambda _=0: self.update_player_ui())
        self.player.playbackStateChanged.connect(self._sync_playback_state)
        self.player.errorOccurred.connect(
            lambda _err, text="": self.win.log(f"خطای پخش صدا: {text}", "error"))

        self.connect_signals()
        self.start_hardware_monitor()
        self.win.showMaximized()
        self.win.log("برنامه آماده است.", "ok")

    # ==========================================
    # اتصال سیگنال‌ها
    # ==========================================
    def connect_signals(self):
        w = self.win
        w.media_open_requested.connect(self.load_media)
        w.asr_open_requested.connect(self.load_raw_text)
        w.corrected_open_requested.connect(self.load_corrected_text)
        w.issues_open_requested.connect(self.load_issues_text)
        w.issues_paste_requested.connect(self.paste_issues)

        w.media_row.removed.connect(self.on_media_removed)
        w.asr_row.removed.connect(self.on_raw_removed)
        w.corrected_row.removed.connect(self.on_corrected_removed)
        w.issues_row.removed.connect(self.on_issues_removed)

        w.process_requested.connect(self.start_processing)
        w.cancel_requested.connect(self.cancel_processing)
        w.apply_requested.connect(self.start_text_sync)
        w.reset_requested.connect(self.reset_all)
        w.edit_start_requested.connect(self.start_edit)
        w.edit_save_requested.connect(self.save_edit)
        w.edit_cancel_requested.connect(self.cancel_edit)

        w.play_toggled.connect(self.toggle_play)
        w.seek_requested.connect(self.seek_audio)
        w.skip_requested.connect(self.skip_audio_relative)
        w.speed_changed.connect(lambda s: self.player.setPlaybackRate(s))
        w.volume_changed.connect(lambda v: self.audio_output.setVolume(v / 100.0))

        w.word_clicked.connect(self.on_word_clicked)
        w.editor.word_action.connect(self.on_word_action)
        w.follow_toggled.connect(self.set_follow)
        w.locate_requested.connect(self.locate_playhead)

        panel = w.issues_panel
        panel.locate_requested.connect(self.on_issue_locate)
        panel.accept_requested.connect(self.on_issue_accept)
        panel.undo_requested.connect(self.undo_accept)
        panel.resolve_requested.connect(self.on_issue_resolve)
        panel.restore_requested.connect(self.on_issue_restore)
        panel.delete_requested.connect(self.on_issue_delete)

        w.nav_changed.connect(self.on_nav_changed)
        w.monitor_page.export_requested.connect(self.export_monitor)
        w.monitor_page.reset_requested.connect(self.reset_monitor)
        w.log_page.export_requested.connect(self.export_log)

    # ==========================================
    # ورودی‌ها — هر متن را می‌توان هر زمان (حتی بعد از پردازش) عوض کرد
    # ==========================================
    def _pick_text(self, title):
        path, _ = QFileDialog.getOpenFileName(self.win, title, "", "Docs (*.txt *.docx)")
        if not path:
            return None, None
        try:
            return path, extract_text_from_file(path)
        except Exception as exc:
            self.win.log(f"خطا در خواندن فایل: {exc}", "error")
            QMessageBox.critical(self.win, "خطا", f"فایل خوانده نشد:\n{exc}")
            return None, None

    def working_text(self):
        """متنی که با صوت همگام و نمایش داده می‌شود: اصلاح‌شده (اگر هست)، وگرنه خام."""
        return self.corrected_text.strip() or self.raw_text.strip()

    def _show_working_text(self):
        """قبل از تحلیل، متن ورودی بدون زمان‌بندی در ادیتور نمایش داده می‌شود (قابل‌ویرایش)."""
        if self.words:
            return
        text = self.working_text()
        self.win.editor.set_paragraphs(paragraphs_from_text(text) if text else [])

    def load_media(self):
        path, _ = QFileDialog.getOpenFileName(
            self.win, "انتخاب صوت", "", "Audio/Video (*.mp3 *.wav *.m4a *.mp4 *.flac *.ogg *.mkv *.webm)")
        if not path:
            return
        self.audio_path = path
        self.cached_asr_words = None
        self.win.set_sync_available(False)
        size = os.path.getsize(path) / (1024 * 1024)
        self.win.set_media_info(os.path.basename(path), f"{size:.1f} MB")
        self.player.setSource(QUrl.fromLocalFile(path))
        self.win.log(f"صوت بارگذاری شد: {path}")
        if self.words:
            self.win.log("⚠ صوت عوض شد؛ برای تطبیق با صوت جدید دوباره «تحلیل» را بزنید.", "warn")

        self.win.wave.clear_peaks()
        self.win.wave.set_loading(True)
        worker = WaveformThread(path)
        worker.ready.connect(lambda peaks, w=worker: self._on_wave(peaks, w))
        worker.failed.connect(lambda err, w=worker: self._on_wave_failed(err, w))
        self.wave_worker = worker
        worker.start()

    def _on_wave(self, peaks, worker):
        if worker is self.wave_worker:
            self.win.set_waveform(peaks)

    def _on_wave_failed(self, err, worker):
        if worker is self.wave_worker:
            self.win.wave.set_loading(False)
            self.win.log(f"⚠ موج صوتی ساخته نشد (پردازش اصلی تأثیری نمی‌پذیرد): {err}", "warn")

    def load_raw_text(self):
        path, text = self._pick_text("انتخاب متن خام")
        if text is None:
            return
        self.raw_text = text
        self.win.set_raw_info(os.path.basename(path), f"{len(text.split())} کلمه")
        self.win.log(f"متن خام بارگذاری شد: {path}")
        self.on_inputs_changed()
        self._show_working_text()

    def load_corrected_text(self):
        path, text = self._pick_text("انتخاب متن اصلاح‌شده")
        if text is None:
            return
        self.corrected_text = text
        self.win.set_corrected_info(os.path.basename(path), f"{len(text.split())} کلمه")
        self.win.log(f"متن اصلاح‌شده بارگذاری شد: {path}")
        self.on_inputs_changed()
        self._show_working_text()

    def load_issues_text(self):
        path, text = self._pick_text("انتخاب فایل ایرادات")
        if text is None:
            return
        self._set_issues(text, os.path.basename(path))

    def paste_issues(self, text):
        self._set_issues(text, "متن چسبانده‌شده")

    def _set_issues(self, text, label):
        self.issues_text = text
        self.overrides.clear()                       # لیست جدید = تصمیم‌های قبلی بی‌اعتبار
        n = len(parse_issue_blocks(text))
        self.win.set_issues_info(label, f"{n} ایراد")
        self.win.log(f"لیست ایرادات بارگذاری شد: {n} مورد.")
        self.on_inputs_changed()

    # ---- حذف ورودی‌ها ----
    def on_media_removed(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.audio_path = None
        self.cached_asr_words = None
        self.wave_worker = None
        self.win.wave.clear_peaks()
        self.win.set_audio_position(0, 0)
        self.win.set_playing(False)
        self.win.set_sync_available(False)

    def on_raw_removed(self):
        self.raw_text = ""
        self.on_inputs_changed()
        self._show_working_text()

    def on_corrected_removed(self):
        self.corrected_text = ""
        self.on_inputs_changed()
        self._show_working_text()

    def on_issues_removed(self):
        self.issues_text = ""
        self.overrides.clear()
        self.on_inputs_changed()

    # ==========================================
    # ویرایش متن داخل برنامه
    # ==========================================
    def _restore_display(self):
        if self.words:
            self.win.editor.set_paragraphs(self._paragraphs())
            self._apply_statuses()
        else:
            self._show_working_text()

    def start_edit(self):
        text = self.working_text()
        if not text:
            return QMessageBox.information(self.win, "ویرایش", "ابتدا یک متن (خام یا اصلاح‌شده) بارگذاری کنید.")
        self.win.editor.begin_edit(paragraphs_from_text(text))
        self.win.set_edit_mode(True)
        self.win.log("حالت ویرایش متن؛ پس از پایان «ذخیره‌ی ویرایش» را بزنید.")

    def save_edit(self):
        text = self.win.editor.end_edit().strip()
        self.win.set_edit_mode(False)
        if not text:
            self._restore_display()
            return self.win.log("⚠ متن خالی ذخیره نشد.", "warn")
        if text == self.working_text():
            self._restore_display()
            return self.win.log("تغییری در متن ایجاد نشده بود.")
        # نسخه‌ی ویرایش‌شده = «متن اصلاح‌شده»؛ متن خام دست‌نخورده می‌ماند (برای تشخیص ایرادات اصلاح‌شده)
        self.corrected_text = text
        self._accept_history.clear()
        self.win.set_corrected_info("ویرایش‌شده در برنامه", f"{len(text.split())} کلمه")
        self.win.log("✓ متن ویرایش‌شده به‌عنوان «متن اصلاح‌شده» ثبت شد.", "ok")
        if self.cached_asr_words:
            self.start_text_sync()          # ذخیره‌ی ویرایش یک اقدام صریح کاربر است
        else:
            self._show_working_text()
            self.win.refresh_action_state()

    def cancel_edit(self):
        self.win.editor.end_edit()
        self.win.set_edit_mode(False)
        self._restore_display()

    # ==========================================
    # ریست کامل (آماده‌ی فایل بعدی)
    # ==========================================
    def reset_all(self):
        answer = QMessageBox.question(
            self.win, "ریست",
            "همه‌ی فایل‌ها، متن‌ها، ایرادات و نتایج پاک شوند و برنامه برای فایل بعدی آماده شود؟\n"
            "(تنظیمات مدل و رنگ‌ها حفظ می‌شود.)")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.player.stop()
        self.player.setSource(QUrl())
        self.audio_path = None
        self.raw_text = self.corrected_text = self.issues_text = ""
        self.cached_asr_words = None
        self.words, self.starts, self.statuses, self.issues = [], [], [], []
        self.overrides.clear()
        self._accept_history.clear()
        self.manual_anchors.clear()
        self._text_key = None
        self.current_word = -1
        self._pending_resync = False
        self.wave_worker = None
        self.win.reset_view()
        self.win.log("ریست شد؛ برنامه برای فایل بعدی آماده است.", "ok")

    def on_inputs_changed(self):
        """پردازش خودکار نیست: اگر صوت قبلاً تحلیل شده، فقط دکمه‌ی «اعمال» فعال می‌شود."""
        self._accept_history.clear()
        self.win.issues_panel.set_undo_enabled(False)
        self.win.refresh_action_state()
        if self.cached_asr_words:
            self.win.set_inputs_dirty(True)

    # ==========================================
    # کارگرها
    # ==========================================
    def _prune_workers(self):
        self._zombies = [z for z in self._zombies if z.isRunning()]

    def _finish_job(self, status):
        self.recorder.end_stage()
        self.win.set_process_running(False)
        self.win.set_pipeline_status(status)

    def start_processing(self, settings):
        if not self.audio_path or not self.working_text():
            return QMessageBox.warning(self.win, "اخطار", "فایل صوتی و یکی از دو متن لازم است.")
        self._prune_workers()
        self.win.set_process_running(True)
        self.win.set_pipeline_status("در حال پردازش هوش مصنوعی...", 0)
        self.win.log(f"شروع استخراج کلمات با Faster-Whisper (مدل {settings['model']}، دستگاه: {settings['device']})...")
        self.recorder.begin_stage("transcribe", f"| مدل {settings['model']} | دستگاه {settings['device']}")

        worker = AudioProcessorThread(self.audio_path, settings)
        worker.progress.connect(lambda p: self.win.set_process_progress(p, 100))
        worker.status.connect(lambda t: self.win.set_pipeline_status(t))
        worker.timer_update.connect(self.win.proc_time.setText)
        worker.log.connect(self.win.log)
        worker.device_info.connect(lambda t, m=settings["model"]: self._on_device_info(m, t))
        worker.result_ready.connect(self.on_audio_finished)
        worker.error.connect(self.on_worker_error)
        self.audio_worker = worker
        worker.start()

    def _on_device_info(self, model, info):
        self.win.set_engine_badge(f"{model} · {info}")
        self.recorder.set_stage_detail(f"| مدل {model} | {info}")
        self.win.log(f"موتور تشخیص روی {info} اجرا شد.", "ok")

    def cancel_processing(self):
        for name in ("audio_worker", "text_worker"):
            worker = getattr(self, name)
            if worker is not None and worker.isRunning():
                if hasattr(worker, "cancel"):
                    worker.cancel()
                else:
                    worker.blockSignals(True)
                self._zombies.append(worker)
            setattr(self, name, None)
        self._finish_job("آماده (متوقف شده)")
        self.win.log("⚠ عملیات توسط کاربر متوقف شد.", "warn")

    def on_worker_error(self, err_msg):
        self.win.log(f"خطا: {err_msg}", "error")
        self._finish_job("خطا")
        QMessageBox.critical(self.win, "خطا", err_msg)

    def on_audio_finished(self, asr_words, total_time):
        self.recorder.end_stage()
        self.cached_asr_words = asr_words
        self.win.set_sync_available(True)
        self.win.log(f"✓ پردازش صوتی پایان یافت: {len(asr_words)} کلمه در {total_time:.1f} ثانیه", "ok")
        self.start_text_sync()

    def start_text_sync(self, anchors_override=None):
        if not isinstance(anchors_override, dict):
            anchors_override = None
        if not self.cached_asr_words or not self.working_text():
            return
        if self.text_worker is not None and self.text_worker.isRunning():
            self._pending_resync = True        # تغییر جدید حین تطبیق: بعد از پایان دوباره اجرا می‌شود
            return
        self._prune_workers()
        self.win.set_process_running(True)
        self.win.set_pipeline_status("در حال همگام‌سازی متن و صوت...", 50)
        self.recorder.begin_stage("alignment")

        working = self.working_text()
        key = hash(working)
        anchors = (dict(anchors_override) if anchors_override is not None
                   else dict(self.manual_anchors) if key == self._text_key else {})
        other = self.raw_text if self.corrected_text.strip() else ""
        worker = TextSyncThread(working, self.issues_text, self.cached_asr_words, anchors, other)
        worker.result_ready.connect(lambda w, r, t, k=key: self.on_text_synced(w, r, t, k))
        worker.error.connect(self.on_worker_error)
        self.text_worker = worker
        worker.start()

    # ==========================================
    # نمایش نتیجه
    # ==========================================
    def _compute_statuses(self):
        issue_words = set()
        for rec in self.issues:
            if rec["state"] == "open":
                issue_words.update(rec["indices"])
        return ["anchor" if w.get("manual") else ("issue" if i in issue_words else "confirmed")
                for i, w in enumerate(self.words)]

    def _paragraphs(self):
        use_lines = sum(1 for w in self.words if w.get("para_end")) >= 2
        paragraphs, current = [], []
        for i, w in enumerate(self.words):
            current.append((w["word"], self.statuses[i]))
            end = w.get("para_end") if use_lines else w["word"].endswith((".", "؟", "!"))
            if end:
                paragraphs.append(current)
                current = []
        if current:
            paragraphs.append(current)
        return paragraphs

    def _apply_statuses(self):
        new = self._compute_statuses()
        if len(new) == len(self.statuses):
            for i, (a, b) in enumerate(zip(self.statuses, new)):
                if a != b:
                    self.win.editor.set_word_status(i, b)
        self.statuses = new

    def _refresh_issue_ui(self, selected=None):
        panel = self.win.issues_panel
        if selected is not None:
            panel._selected = selected
        panel.refresh()
        self.win.update_issue_summary()

    def on_text_synced(self, words, records, total_time, key):
        self.recorder.end_stage()
        self.text_worker = None
        self._text_key = key
        self.words = words
        self.starts = [w["start"] for w in words]
        self.manual_anchors = {i: w["manual_start"] for i, w in enumerate(words) if w.get("manual")}
        self.current_word = -1

        for rec in records:                           # تصمیم‌های قبلی کاربر (حل‌شده/حذف) حفظ می‌شود
            decision = self.overrides.get(rec["key"])
            if decision == "deleted":
                rec["state"] = "deleted"
            elif decision == "accepted":
                rec.update(state="resolved", accepted=True, indices=[])
            elif decision == "resolved" and rec["state"] in ("open", "missing"):
                rec["state"] = "resolved"
        self.issues = records

        self.statuses = self._compute_statuses()
        self.win.editor.set_paragraphs(self._paragraphs())
        self.win.issues_panel.set_records(records)
        self.win.issues_panel.set_undo_enabled(bool(self._accept_history))
        self.win.update_issue_summary()

        self.win.set_inputs_dirty(False)
        self.win.set_process_running(False)
        self.win.set_process_progress(100, 100)
        self.win.set_pipeline_status("✓ آماده", 100)
        self.win.lbl_stats.setText(f"کلمات: {len(words)} | زمان تطبیق: {total_time:.1f}s")
        c = self.win.issues_panel.counts()
        self.win.log(
            f"✓ تطبیق کامل شد: {len(words)} کلمه | ایرادات: {c['open']} باز، {c['resolved']} حل‌شده، {c['missing']} پیدا نشد.", "ok")
        missing = [r for r in records if r["state"] == "missing"]
        if missing:
            names = "، ".join(f"#{r['number']}" for r in missing[:8])
            self.win.log(f"⚠ ایرادات پیدا‌نشده: {names} — عبارت باید عیناً از متن کپی شده باشد.", "warn")
        self.update_player_ui()
        if self._pending_resync:
            self._pending_resync = False
            self.start_text_sync()

    # ==========================================
    # ایرادات
    # ==========================================
    def on_issue_locate(self, idx):
        rec = self.issues[idx]
        if rec["state"] != "open" or not rec["indices"]:
            return
        self.win.issues_panel.select(idx)
        self.win.update_issue_summary()
        self.goto_word(rec["indices"][0], play=None)
        self.win.editor.set_focus_span(rec["indices"])

    def _set_state(self, idx, state):
        rec = self.issues[idx]
        rec["state"] = state
        if state in ("resolved", "deleted"):
            self.overrides[rec["key"]] = state
        else:
            self.overrides.pop(rec["key"], None)
        self._apply_statuses()
        self._refresh_issue_ui()

    def _rebuild_text_with(self, a, b, new_words):
        """متن را از روی کلمه‌ها می‌سازد و بازه‌ی a..b را با کلمه‌های جدید عوض می‌کند."""
        tokens = [w["word"] for w in self.words]
        para = [bool(w.get("para_end")) for w in self.words]
        first, last = tokens[a], tokens[b]
        lead = re.match(r"^[^\w]+", first)
        trail = re.search(r"[^\w]+$", last)
        new_words = list(new_words)
        if lead and not new_words[0][:1] in lead.group():
            new_words[0] = lead.group() + new_words[0]
        if trail and not re.search(r"[^\w]$", new_words[-1]):
            new_words[-1] += trail.group()
        tokens = tokens[:a] + new_words + tokens[b + 1:]
        para = para[:a] + [False] * (len(new_words) - 1) + [para[b]] + para[b + 1:]
        text = ""
        for tok, end in zip(tokens, para):
            text += tok + ("\n" if end else " ")
        return text.strip(), len(new_words) - (b - a + 1)

    def on_issue_accept(self, idx):
        rec = self.issues[idx]
        fix = (rec["fix"] or "").strip()
        if rec["state"] != "open" or not rec["indices"] or not has_fix(fix):
            return
        a, b = rec["indices"][0], rec["indices"][-1]
        old_phrase = " ".join(w["word"] for w in self.words[a:b + 1])
        new_text, delta = self._rebuild_text_with(a, b, fix.split())
        anchors = {}
        for i, t in self.manual_anchors.items():
            if i < a:
                anchors[i] = t
            elif i > b:
                anchors[i + delta] = t
        self._accept_history.append({
            "key": rec["key"], "corrected": self.corrected_text, "raw_was_working": not self.corrected_text.strip(),
            "anchors": dict(self.manual_anchors), "old": old_phrase, "new": fix})
        self.corrected_text = new_text
        self.overrides[rec["key"]] = "accepted"
        self.win.set_corrected_info("اعمال‌شده در برنامه", f"{len(new_text.split())} کلمه")
        self.win.editor.set_focus_span([])
        self.win.log(f"✓ جایگزین شد: «{old_phrase}» ← «{fix}»", "ok")
        self.start_text_sync(anchors_override=anchors)

    def undo_accept(self):
        if not self._accept_history:
            return
        h = self._accept_history.pop()
        self.corrected_text = h["corrected"]
        self.overrides.pop(h["key"], None)
        if self.corrected_text.strip():
            self.win.set_corrected_info("اعمال‌شده در برنامه", f"{len(self.corrected_text.split())} کلمه")
        else:
            self.win.corrected_row.clear()
            self.win.refresh_action_state()
        self.win.log(f"↶ جایگزینی برگردانده شد: «{h['new']}» ← «{h['old']}»")
        self.start_text_sync(anchors_override=h["anchors"])

    def on_issue_resolve(self, idx):
        self._set_state(idx, "resolved")
        self.win.editor.set_focus_span([])
        nxt = self.win.issues_panel.next_open_after(idx)
        if nxt is not None:
            self.on_issue_locate(nxt)

    def on_issue_restore(self, idx):
        rec = self.issues[idx]
        rec["auto_resolved"] = False
        self._set_state(idx, "open" if rec["indices"] else "missing")
        self.overrides.pop(rec["key"], None)

    def on_issue_delete(self, idx):
        self._set_state(idx, "deleted")
        self.win.editor.set_focus_span([])

    # ==========================================
    # پخش، پرش و دنبال‌کردن
    # ==========================================
    def _sync_playback_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.win.set_playing(playing)
        if playing:
            self.follower_timer.start()
        else:
            self.follower_timer.stop()

    def toggle_play(self, play_intent):
        if play_intent:
            self.player.play()
        else:
            self.player.pause()

    def seek_audio(self, fraction):
        dur = self.player.duration()
        if dur > 0:
            self.player.setPosition(int(fraction * dur))

    def skip_audio_relative(self, ms_offset):
        dur = self.player.duration()
        if dur > 0:
            self.player.setPosition(max(0, min(dur, self.player.position() + ms_offset)))

    def update_player_ui(self):
        dur = self.player.duration()
        if dur <= 0:
            return
        pos = self.player.position()
        self.win.set_audio_position(pos, dur)
        if self.follow and self.starts:
            self._follow(pos / 1000.0)

    def _word_index_at(self, t):
        return bisect.bisect_right(self.starts, t) - 1

    def _follow(self, t):
        idx = self._word_index_at(t)
        if idx < 0 or t > self.words[idx]["end"] + 0.6:
            return
        if idx != self.current_word:
            self.current_word = idx
            self.win.editor.set_active_word(idx, scroll=True)

    def set_follow(self, on):
        self.follow = bool(on)
        self.current_word = -1
        if self.follow:
            self.locate_playhead()
        else:
            self.win.editor.clear_active()

    def locate_playhead(self):
        """نشان می‌دهد صدا همین الان کجای متن است (یک‌بار)."""
        if not self.words:
            return self.win.log("⚠ هنوز متنی همگام نشده است.", "warn")
        idx = max(0, self._word_index_at(self.player.position() / 1000.0))
        self.win.editor.scroll_to_word(idx)
        self.win.editor.set_active_word(idx, scroll=False)
        self.current_word = idx

    def goto_word(self, idx, play=None):
        """پرش صدا + متن به یک کلمه. play: True پخش، False مکث، None بدون تغییر."""
        if not 0 <= idx < len(self.words):
            return
        self.player.setPosition(int(self.words[idx]["start"] * 1000))
        if play is True:
            self.player.play()
        elif play is False:
            self.player.pause()
        self.win.editor.scroll_to_word(idx)
        self.win.editor.set_active_word(idx, scroll=False)
        self.current_word = idx

    # ==========================================
    # کلیک روی کلمه
    #   Ctrl+Click: پخش از همان کلمه | Alt+Click / F2: «صدا همین‌جاست»
    # ==========================================
    def on_word_clicked(self, word_id, flags):
        if not 0 <= int(word_id) < len(self.words):
            return
        if flags & MOD_ALT:
            self.set_anchor(int(word_id))
        elif flags & MOD_CTRL:
            self.play_from_word(int(word_id))

    def on_word_action(self, word_id, action):
        if action == "play":
            self.play_from_word(word_id)
        elif action == "anchor":
            self.set_anchor(word_id)
        elif action == "unanchor":
            self.remove_anchor(word_id)

    def play_from_word(self, idx):
        if not 0 <= idx < len(self.words):
            return
        self.player.setPosition(int(self.words[idx]["start"] * 1000))
        self.player.play()
        self.win.set_playing(True)
        self.win.editor.set_active_word(idx, scroll=False)
        self.current_word = idx
        self.win.log(f"⏱ پخش از «{self.words[idx]['word']}» ({clock(self.words[idx]['start'])})")

    def _after_timing_change(self):
        self.starts = [w["start"] for w in self.words]
        self.manual_anchors = {i: w["manual_start"] for i, w in enumerate(self.words) if w.get("manual")}
        self.current_word = -1
        self._apply_statuses()

    def set_anchor(self, idx):
        if not 0 <= idx < len(self.words):
            return
        t = self.player.position() / 1000.0
        set_manual_anchor(self.words, idx, t)
        self._after_timing_change()
        self.win.log(f"📍 لنگر دستی: «{self.words[idx]['word']}» ← {clock(t)}")

    def remove_anchor(self, idx):
        if 0 <= idx < len(self.words) and self.words[idx].get("manual"):
            clear_manual_anchor(self.words, idx)
            self._after_timing_change()
            self.win.log(f"لنگر دستی «{self.words[idx]['word']}» حذف شد.")

    # ==========================================
    # سخت‌افزار و گزارش‌ها
    # ==========================================
    def start_hardware_monitor(self):
        self.hw_monitor = HardwareMonitor()
        self.hw_monitor.update_stats.connect(self.update_hw_ui)
        self.hw_monitor.start()

    @staticmethod
    def _pct(v):
        return "—" if v is None else f"{v:.0f}%"

    def update_hw_ui(self, s):
        self.recorder.add(s)
        self.win.monitor_page.update_stats(s, self.recorder.current_stage)

        if s.get("has_gpu"):
            temp = s.get("gpu_temp")
            text = (f"GPU {self._pct(s.get('gpu_util'))}"
                    + (f" · {temp:.0f}°C" if temp is not None else "")
                    + f" | VRAM {self._pct(s.get('vram_pct'))} | CPU {s['cpu']:.0f}% | RAM {s['ram']:.0f}%")
            level = level_for_temp(temp)
            self.win.set_gpu_status(text, "ok" if level == "na" else level)
        else:
            self.win.set_gpu_status(f"CPU {s['cpu']:.0f}% | RAM {s['ram']:.0f}% | بدون GPU", "warn")

        self._tick += 1
        if self._tick % 3 == 0 and self.win.main_stack.currentIndex() == 1:
            self.win.monitor_page.set_summary(self.recorder.summary())

    def on_nav_changed(self, key):
        if key == "monitor":
            self.win.monitor_page.set_summary(self.recorder.summary())

    def reset_monitor(self):
        self.recorder.reset()
        self.win.monitor_page.clear()
        self.win.monitor_page.set_summary(self.recorder.summary())
        self.win.log("نشست مانیتورینگ از نو شروع شد.")

    def export_monitor(self, kind):
        filters = {"txt": "Text (*.txt)", "json": "JSON (*.json)", "csv": "CSV (*.csv)"}
        default = f"Natiq_Hardware_{time.strftime('%Y%m%d_%H%M')}.{kind}"
        path, _ = QFileDialog.getSaveFileName(self.win, "ذخیره گزارش مانیتورینگ", default, filters[kind])
        if not path:
            return
        try:
            {"txt": self.recorder.export_text, "json": self.recorder.export_json,
             "csv": self.recorder.export_csv}[kind](path)
        except Exception as exc:
            self.win.log(f"خطا در ذخیره‌ی گزارش: {exc}", "error")
            return QMessageBox.critical(self.win, "خطا", str(exc))
        self.win.log(f"✓ گزارش مانیتورینگ ذخیره شد: {path}", "ok")
        QMessageBox.information(self.win, "موفق", "گزارش با موفقیت ذخیره شد.")

    def export_log(self):
        default = f"Natiq_Log_{time.strftime('%Y%m%d_%H%M')}.txt"
        path, _ = QFileDialog.getSaveFileName(self.win, "ذخیره لاگ", default, "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.win.log_page.as_text())
            QMessageBox.information(self.win, "موفق", "لاگ با موفقیت ذخیره شد.")

    # ==========================================
    # خروج
    # ==========================================
    def shutdown(self):
        for name in ("audio_worker", "text_worker"):
            worker = getattr(self, name)
            if worker is not None and worker.isRunning():
                if hasattr(worker, "cancel"):
                    worker.cancel()
                worker.wait(2000)
        if self.wave_worker is not None and self.wave_worker.isRunning():
            self.wave_worker.wait(2000)
        if self.hw_monitor is not None:
            self.hw_monitor.stop()
        self.player.stop()


if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    load_fonts()
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(build_qss())

    win = MainWindow()
    controller = AppController(win)
    app.aboutToQuit.connect(controller.shutdown)
    sys.exit(app.exec())
