@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
REM ------------------------------------------------------------------
REM  ساخت Natiq Studio روی ویندوز (یک‌بار، روی سیستم دارای اینترنت)
REM  استفاده:   build_windows.bat          ← نسخه‌ی کامل (GPU + CPU)
REM             build_windows.bat cpu      ← نسخه‌ی سبک بدون CUDA
REM  خروجی:     installer_out\NatiqStudio_Setup.exe
REM ------------------------------------------------------------------
set MODE=%1
if /I "%MODE%"=="cpu" (set NATIQ_GPU=0) else (set NATIQ_GPU=1)

where py >nul 2>nul || (echo [خطا] Python 3.11 یا 3.12 نصب نیست: https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv (py -3.11 -m venv .venv || py -3 -m venv .venv)
call .venv\Scripts\activate.bat || (echo [خطا] venv & pause & exit /b 1)

python -m pip install --upgrade pip || goto :fail
pip install -r requirements.txt || goto :fail
if "%NATIQ_GPU%"=="1" (pip install -r requirements-gpu.txt || goto :fail)

echo.
echo === دانلود مدل‌های همراه برنامه (فقط همین یک‌بار) ===
python tools\fetch_models.py base small || goto :fail

echo.
echo === ساخت برنامه ===
pyinstaller --noconfirm --clean natiq.spec || goto :fail

set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
  echo === ساخت فایل نصب ===
  %ISCC% installer.iss || goto :fail
  echo.
  echo ✓ آماده: installer_out\NatiqStudio_Setup.exe
) else (
  echo.
  echo Inno Setup 6 پیدا نشد؛ برنامه‌ی قابل‌اجرا در dist\NatiqStudio\NatiqStudio.exe آماده است.
  echo برای ساخت فایل نصب: https://jrsoftware.org/isdl.php و دوباره اجرا.
)
pause
exit /b 0

:fail
echo.
echo [خطا] ساخت ناموفق بود؛ پیام‌های بالا را بررسی کنید.
pause
exit /b 1
