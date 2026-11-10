# ساخت فایل نصب (ویندوز ۱۰ و ۱۱)

۱. روی یک سیستم ویندوزی با اینترنت: Python 3.11 (تیک Add to PATH) و Inno Setup 6 را نصب کنید.
۲. (توصیه‌شده) فونت‌های Vazirmatn را در assets/fonts بگذارید.
۳. روی `build_windows.bat` دوبار کلیک کنید  (یا `build_windows.bat cpu` برای نسخه‌ی سبک).
۴. خروجی: `installer_out\NatiqStudio_Setup.exe` — فقط همین یک فایل را به هر کامپیوتر بدهید.
   روی سیستم مقصد: نصب ← اجرا. اینترنت، Python یا CUDA جداگانه لازم نیست.

* نسخه‌ی کامل: CUDA/cuDNN و مدل‌های base و small داخل نصب‌کننده است. اگر کارت NVIDIA و درایور باشد از GPU استفاده می‌کند، وگرنه خودکار CPU.
* مدل‌های دیگر (tiny/medium/large-v3): `python tools\fetch_models.py medium` را قبل از ساخت اجرا کنید.
* اولین اجرا ممکن است SmartScreen هشدار «ناشناس» بدهد (برنامه امضای دیجیتال ندارد). «More info ← Run anyway».
