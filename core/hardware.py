"""پایش سخت‌افزار و ضبط گزارش عملکرد نشست.

- HardwareMonitor: نخ پایش (CPU/RAM/GPU/VRAM/دما/توان). سنسور ناموجود = None (نه صفر).
- SessionRecorder: ثبت نمونه‌ها و مراحل پردازش و ساخت گزارش (CSV / JSON / TXT).
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import time

import psutil
from PySide6.QtCore import QThread, Signal

try:
    import pynvml
    pynvml.nvmlInit()
    HAS_NVML = True
except Exception:
    pynvml = None
    HAS_NVML = False

HAS_NVIDIA = HAS_NVML or bool(shutil.which("nvidia-smi"))

METRIC_INFO = {
    "cpu":       ("پردازنده (CPU)", "%"),
    "ram":       ("حافظه RAM", "%"),
    "gpu_util":  ("بار GPU", "%"),
    "vram_pct":  ("حافظه GPU (VRAM)", "%"),
    "gpu_temp":  ("دمای GPU", "°C"),
    "cpu_temp":  ("دمای CPU", "°C"),
    "gpu_power_w": ("توان GPU", "W"),
}
KEYS = ["cpu", "ram", "gpu_util", "vram_pct", "gpu_temp", "cpu_temp", "gpu_power_w",
        "vram_used_mb", "vram_total_mb", "gpu_clock_mhz", "app_ram_mb", "app_cpu"]
STAGE_LABELS = {
    "idle": "بیکار",
    "transcribe": "تشخیص گفتار (Whisper)",
    "alignment": "همگام‌سازی متن",
}


def level_for_temp(value, warn=75, bad=85):
    if value is None:
        return "na"
    return "bad" if value >= bad else "warn" if value >= warn else "ok"


def level_for_percent(value, warn=80, bad=92):
    if value is None:
        return "na"
    return "bad" if value >= bad else "warn" if value >= warn else "ok"


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ==========================================
# خوانندگان GPU
# ==========================================
class _NvmlGpu:
    def __init__(self):
        self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(self.handle)
        self.name = name.decode() if isinstance(name, bytes) else str(name)

    def read(self):
        out = {"has_gpu": True, "gpu_name": self.name}
        h = self.handle
        try:
            out["gpu_util"] = float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        except Exception:
            pass
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            out["vram_used_mb"] = mem.used / 2**20
            out["vram_total_mb"] = mem.total / 2**20
            out["vram_pct"] = mem.used / mem.total * 100 if mem.total else None
        except Exception:
            pass
        try:
            out["gpu_temp"] = float(pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU))
        except Exception:
            pass
        try:
            out["gpu_power_w"] = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
        except Exception:
            pass
        try:
            out["gpu_clock_mhz"] = float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_GRAPHICS))
        except Exception:
            pass
        return out


class _SmiGpu:
    """جایگزین وقتی pynvml نصب نیست ولی nvidia-smi وجود دارد."""
    CMD = ["nvidia-smi",
           "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,clocks.gr",
           "--format=csv,noheader,nounits"]

    def __init__(self):
        self.name = ""
        self.read()                       # اگر خطا بدهد سازنده شکست می‌خورد

    def read(self):
        flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
        res = subprocess.run(self.CMD, capture_output=True, text=True, timeout=4, creationflags=flags)
        line = res.stdout.strip().splitlines()[0]
        p = [x.strip() for x in line.split(",")]
        self.name = p[0]
        used, total = _num(p[2]), _num(p[3])
        return {
            "has_gpu": True, "gpu_name": self.name,
            "gpu_util": _num(p[1]), "vram_used_mb": used, "vram_total_mb": total,
            "vram_pct": used / total * 100 if used is not None and total else None,
            "gpu_temp": _num(p[4]), "gpu_power_w": _num(p[5]), "gpu_clock_mhz": _num(p[6]),
        }


# ==========================================
# نخ پایش
# ==========================================
class HardwareMonitor(QThread):
    update_stats = Signal(dict)

    def __init__(self, interval_ms=1000):
        super().__init__()
        self.running = True
        self.interval_ms = interval_ms
        self._gpu = None
        self._wmi = None
        self._proc = psutil.Process()
        self._ncpu = psutil.cpu_count() or 1
        psutil.cpu_percent(None)
        self._proc.cpu_percent(None)

    # ---- راه‌اندازی سنسورها (داخل نخ پایش) ----
    def _init_sensors(self):
        if HAS_NVML:
            try:
                self._gpu = _NvmlGpu()
            except Exception:
                self._gpu = None
        if self._gpu is None and shutil.which("nvidia-smi"):
            try:
                self._gpu = _SmiGpu()
            except Exception:
                self._gpu = None
        if os.name == "nt" and not hasattr(psutil, "sensors_temperatures"):
            try:                                   # اختیاری: LibreHardwareMonitor باز باشد
                import pythoncom
                import wmi
                pythoncom.CoInitialize()
                for ns in ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"):
                    try:
                        self._wmi = wmi.WMI(namespace=ns)
                        self._wmi.Sensor(SensorType="Temperature")
                        break
                    except Exception:
                        self._wmi = None
            except Exception:
                self._wmi = None

    def _cpu_temp(self):
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                for key in ("coretemp", "k10temp", "cpu_thermal", "zenpower"):
                    if temps.get(key):
                        return max(t.current for t in temps[key])
            if self._wmi is not None:
                vals = [(s.Name, float(s.Value)) for s in self._wmi.Sensor(SensorType="Temperature")
                        if "cpu" in str(s.Identifier).lower()]
                for name, v in vals:
                    if "package" in name.lower() or "tdie" in name.lower() or "tctl" in name.lower():
                        return v
                if vals:
                    return max(v for _, v in vals)
        except Exception:
            pass
        return None

    def _collect(self):
        vm = psutil.virtual_memory()
        stats = {
            "ts": time.time(),
            "cpu": psutil.cpu_percent(None), "cpu_temp": self._cpu_temp(),
            "ram": vm.percent, "ram_used_gb": vm.used / 2**30, "ram_total_gb": vm.total / 2**30,
            "app_ram_mb": self._proc.memory_info().rss / 2**20,
            "app_cpu": self._proc.cpu_percent(None) / self._ncpu,
            "has_gpu": False, "gpu_name": "",
            "gpu_util": None, "vram_pct": None, "vram_used_mb": None, "vram_total_mb": None,
            "gpu_temp": None, "gpu_power_w": None, "gpu_clock_mhz": None,
        }
        if self._gpu is not None:
            try:
                stats.update(self._gpu.read())
            except Exception:
                pass
        return stats

    def run(self):
        self._init_sensors()
        while self.running:
            try:
                self.update_stats.emit(self._collect())
            except Exception:
                pass
            waited = 0
            while self.running and waited < self.interval_ms:
                self.msleep(100)
                waited += 100

    def stop(self):
        self.running = False
        self.wait(3000)


# ==========================================
# ضبط نشست و گزارش
# ==========================================
def _clock(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


def _agg(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {"min": min(vals), "avg": sum(vals) / len(vals), "max": max(vals)}


class SessionRecorder:
    def __init__(self, max_samples=43200):
        self.max_samples = max_samples
        self.reset()

    def reset(self):
        self.started = time.time()
        self.samples, self.stages, self.events = [], [], []
        self._open = None
        self.gpu_name, self.has_gpu = "", False

    @property
    def current_stage(self):
        return self._open["name"] if self._open else "idle"

    def add(self, stats):
        row = {"ts": stats["ts"], "stage": self.current_stage}
        for k in KEYS:
            row[k] = stats.get(k)
        self.samples.append(row)
        if len(self.samples) > self.max_samples:
            del self.samples[: len(self.samples) - self.max_samples]
        if stats.get("has_gpu"):
            self.has_gpu, self.gpu_name = True, stats.get("gpu_name", "")

    def event(self, text):
        self.events.append({"ts": time.time(), "text": text})

    def begin_stage(self, name, detail=""):
        self.end_stage()
        self._open = {"name": name, "detail": detail, "start": time.time(), "end": None}
        self.stages.append(self._open)
        self.event(f"شروع: {STAGE_LABELS.get(name, name)} {detail}".strip())

    def set_stage_detail(self, detail):
        if self._open:
            self._open["detail"] = detail

    def end_stage(self):
        if self._open:
            self._open["end"] = time.time()
            self.event(f"پایان: {STAGE_LABELS.get(self._open['name'], self._open['name'])}")
            self._open = None

    # ---- خلاصه ----
    def _metrics(self, rows, keys):
        out = {}
        for k in keys:
            agg = _agg(r[k] for r in rows)
            if agg:
                peak = max((r for r in rows if r[k] is not None), key=lambda r: r[k])
                agg["max_at"] = _clock(peak["ts"])
                out[k] = agg
        return out

    def summary(self):
        now = time.time()
        main_keys = list(METRIC_INFO)
        metrics = self._metrics(self.samples, main_keys)

        stages = []
        for st in self.stages:
            end = st["end"] or now
            rows = [r for r in self.samples if st["start"] <= r["ts"] <= end]
            stages.append({
                "name": st["name"], "label": STAGE_LABELS.get(st["name"], st["name"]),
                "detail": st["detail"], "start": _clock(st["start"]),
                "duration_s": end - st["start"], "running": st["end"] is None,
                "samples": len(rows), "metrics": self._metrics(rows, main_keys),
            })

        warnings = []
        gt = metrics.get("gpu_temp")
        if gt:
            if gt["max"] >= 85:
                warnings.append(f"دمای GPU به {gt['max']:.0f}°C رسید (خطرناک؛ خنک‌کننده و جریان هوا را بررسی کنید).")
            elif gt["max"] >= 75:
                warnings.append(f"دمای GPU تا {gt['max']:.0f}°C بالا رفت (گرم ولی قابل‌قبول).")
        vp = metrics.get("vram_pct")
        if vp and vp["max"] >= 92:
            warnings.append(f"حافظه GPU تا {vp['max']:.0f}٪ پر شد؛ مدل کوچک‌تر یا int8 را امتحان کنید.")
        rp = metrics.get("ram")
        if rp and rp["max"] >= 92:
            warnings.append(f"RAM سیستم تا {rp['max']:.0f}٪ پر شد.")
        ct = metrics.get("cpu_temp")
        if ct and ct["max"] >= 90:
            warnings.append(f"دمای CPU به {ct['max']:.0f}°C رسید.")
        if not self.has_gpu:
            warnings.append("GPU شناسایی نشد؛ پردازش روی CPU انجام می‌شود (کندتر).")
        else:
            for st in stages:
                if st["name"] == "transcribe":
                    g = st["metrics"].get("gpu_util")
                    if g and g["avg"] < 5 and st["duration_s"] > 20:
                        warnings.append("در مرحله‌ی تشخیص گفتار بار GPU تقریباً صفر بود؛ احتمالاً پردازش روی CPU اجرا شده است.")
        if "cpu_temp" not in metrics:
            warnings.append("دمای CPU در این سیستم قابل خواندن نیست (در ویندوز نیاز به LibreHardwareMonitor).")

        return {
            "started": _clock(self.started), "duration_s": now - self.started,
            "samples": len(self.samples), "has_gpu": self.has_gpu, "gpu_name": self.gpu_name,
            "metrics": metrics, "stages": stages, "warnings": warnings,
            "events": [{"time": _clock(e["ts"]), "text": e["text"]} for e in self.events],
        }

    # ---- خروجی‌ها ----
    def export_csv(self, path):
        cols = ["time", "elapsed_s", "stage"] + KEYS
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in self.samples:
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])),
                            round(r["ts"] - self.started, 1), r["stage"]]
                           + ["" if r[k] is None else round(r[k], 2) for k in KEYS])

    def export_json(self, path):
        data = {"app": "Natiq Studio", "exported": time.strftime("%Y-%m-%d %H:%M:%S"),
                "summary": self.summary(), "samples": self.samples}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def export_text(self, path):
        s = self.summary()
        fmt = lambda a, k: "—" if not a else f"{a[k]:.1f}"
        lines = [
            "گزارش عملکرد سخت‌افزار — Natiq Studio", "=" * 48,
            f"شروع نشست : {s['started']}", f"مدت نشست   : {s['duration_s'] / 60:.1f} دقیقه",
            f"تعداد نمونه: {s['samples']}", f"GPU        : {s['gpu_name'] or 'یافت نشد'}", "",
            "خلاصه‌ی کل نشست", "-" * 48,
        ]
        for k, (label, unit) in METRIC_INFO.items():
            a = s["metrics"].get(k)
            lines.append(f"{label:<22} min {fmt(a, 'min'):>6}  avg {fmt(a, 'avg'):>6}  max {fmt(a, 'max'):>6} {unit}"
                         + (f"  (اوج در {a['max_at']})" if a else "  (سنسور در دسترس نیست)"))
        lines += ["", "مراحل پردازش", "-" * 48]
        if not s["stages"]:
            lines.append("هنوز پردازشی اجرا نشده است.")
        for st in s["stages"]:
            lines.append(f"* {st['label']}  {st['detail']}  | شروع {st['start']} | مدت {st['duration_s']:.0f}s"
                         + (" (در حال اجرا)" if st["running"] else ""))
            for k in ("cpu", "ram", "gpu_util", "vram_pct", "gpu_temp", "gpu_power_w"):
                a = st["metrics"].get(k)
                if a:
                    lines.append(f"    {METRIC_INFO[k][0]:<20} avg {a['avg']:.1f}  max {a['max']:.1f} {METRIC_INFO[k][1]}")
        lines += ["", "هشدارها و نتیجه‌گیری", "-" * 48]
        lines += [f"! {w}" for w in s["warnings"]] or ["مشکلی ثبت نشد."]
        lines += ["", "رویدادها", "-" * 48] + [f"[{e['time']}] {e['text']}" for e in s["events"]]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
