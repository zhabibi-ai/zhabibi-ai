"""استخراج موج صوتی واقعی (peaks) از فایل، بدون وابستگی جدید (از PyAV داخل faster-whisper)."""
from PySide6.QtCore import QThread, Signal


class WaveformThread(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, path, buckets=1600):
        super().__init__()
        self.path = path
        self.buckets = buckets

    def run(self):
        try:
            import numpy as np
            from faster_whisper.audio import decode_audio

            audio = decode_audio(self.path, sampling_rate=4000)
            n = len(audio)
            if n == 0:
                raise ValueError("فایل صوتی خالی است")
            buckets = max(1, min(self.buckets, n))
            edges = np.linspace(0, n, buckets + 1).astype(int)[:-1]
            peaks = np.maximum.reduceat(np.abs(audio), edges)
            ref = float(np.percentile(peaks, 98)) or float(peaks.max()) or 1.0
            peaks = np.clip(peaks / ref, 0.0, 1.0) ** 0.75
            self.ready.emit([max(0.04, float(p)) for p in peaks])
        except Exception as exc:
            self.failed.emit(str(exc))
