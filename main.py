"""
نقطهٔ ورود برنامه: ابزار سنجش سرعت و پایداری سرورهای DNS عمومی.

اجرا:
    python main.py

برای ساخت فایل EXE به README.md مراجعه کنید.
"""

import os
import sys

# اطمینان از اینکه مسیر پروژه (برای import های core و gui) در sys.path هست،
# چه هنگام اجرای مستقیم با پایتون و چه بعد از بسته‌بندی با PyInstaller.
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS  # مسیر موقت داخلی PyInstaller هنگام اجرای EXE
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

from gui.app import launch  # noqa: E402

if __name__ == "__main__":
    providers_json = os.path.join(BASE_DIR, "dns_providers.json")
    launch(providers_json)
