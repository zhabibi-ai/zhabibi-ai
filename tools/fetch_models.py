"""دانلود مدل‌های faster-whisper داخل پوشه‌ی models/ (فقط هنگام ساخت برنامه؛ برنامه‌ی نهایی آفلاین است)."""
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

FILES = ["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "vocabulary.txt",
         "preprocessor_config.json"]

names = sys.argv[1:] or ["base", "small"]
root = Path(__file__).resolve().parent.parent / "models"
for name in names:
    target = root / name
    if (target / "model.bin").is_file():
        print(f"[skip] {name} از قبل موجود است")
        continue
    print(f"[download] {name} ...")
    snapshot_download(repo_id=f"Systran/faster-whisper-{name}", local_dir=str(target), allow_patterns=FILES)
print("تمام شد.")
