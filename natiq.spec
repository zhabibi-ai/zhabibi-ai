# -*- mode: python ; coding: utf-8 -*-
# ساخت:  pyinstaller --noconfirm --clean natiq.spec
# متغیر محیطی NATIQ_GPU=0 → نسخه‌ی سبک بدون CUDA
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

ROOT = Path(SPECPATH)
WITH_GPU = os.environ.get("NATIQ_GPU", "1") != "0"

datas, binaries, hiddenimports = [], [], []
for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "av", "tokenizers", "huggingface_hub", "rapidfuzz"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception as exc:
        print(f"[spec] {pkg}: {exc}")

if WITH_GPU:
    for pkg in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            binaries += collect_dynamic_libs(pkg)
        except Exception as exc:
            print(f"[spec] {pkg} پیدا نشد (نسخه‌ی GPU بدون آن کار نمی‌کند): {exc}")

for folder in ("assets", "models"):
    if (ROOT / folder).is_dir():
        datas.append((str(ROOT / folder), folder))

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["PySide6.QtSvg", "PySide6.QtMultimedia", "pynvml"],
    excludes=["torch", "torchaudio", "torchvision", "tensorflow", "matplotlib", "tkinter",
              "PyQt5", "PyQt6", "IPython", "pytest", "scipy", "pandas"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = ROOT / "assets" / "icon.ico"
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="NatiqStudio",
    console=False,
    icon=str(icon) if icon.is_file() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="NatiqStudio")
