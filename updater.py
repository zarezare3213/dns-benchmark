"""
مدیریت فهرست سرویس‌دهنده‌های DNS شناخته‌شده.

این برنامه ادعا نمی‌کند «همهٔ DNSهای دنیا» را می‌یابد؛ فقط از یک فهرست
دستچین‌شده و قابل‌ویرایش استفاده می‌کند (dns_providers.json). دو راه برای
به‌روزرسانی وجود دارد:
  1) ویرایش دستی فایل JSON توسط کاربر (افزودن/حذف/اصلاح سرور).
  2) وارد کردن (import) یک فایل JSON دیگر با همان ساختار — مثلاً فهرستی
     که کاربر خودش از منابع رسمی هر سرویس‌دهنده جمع‌آوری کرده — و ادغام
     آن با فهرست فعلی (merge بر اساس نام سرویس‌دهنده).

هیچ درخواست خودکاری به اینترنت برای «کشف» DNS جدید زده نمی‌شود؛ این کار
عمداً حذف شده تا از ادعای نادرست «یافتن تمام DNSها» پرهیز شود.
"""

import json
from pathlib import Path


def load_providers(json_path: str | Path) -> dict:
    path = Path(json_path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_providers(data: dict, json_path: str | Path) -> None:
    path = Path(json_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def flatten_to_server_list(data: dict) -> list[dict]:
    """تبدیل ساختار providers.json به لیست تخت از سرورهای منفرد
    برای اجرای مستقیم در ماژول benchmark."""
    servers = []
    for provider in data.get("providers", []):
        name = provider.get("name", "نامشخص")
        for ip in provider.get("ipv4", []):
            servers.append({"provider": name, "ip": ip, "ip_version": "IPv4"})
        for ip in provider.get("ipv6", []):
            servers.append({"provider": name, "ip": ip, "ip_version": "IPv6"})
    return servers


def merge_provider_lists(base: dict, incoming: dict) -> dict:
    """ادغام فهرست جدید (incoming) با فهرست فعلی (base).
    اگر سرویس‌دهنده‌ای با همان نام از قبل وجود داشته باشد، آدرس‌هایش
    به‌روزرسانی می‌شود؛ در غیر این صورت به فهرست اضافه می‌شود."""
    merged = {p["name"]: p for p in base.get("providers", [])}
    for provider in incoming.get("providers", []):
        merged[provider["name"]] = provider
    base["providers"] = list(merged.values())
    return base


def add_custom_server(data: dict, name: str, ipv4: list[str] | None = None,
                       ipv6: list[str] | None = None, source: str = "دستی توسط کاربر") -> dict:
    """افزودن دستی یک سرور DNS جدید به فهرست از داخل برنامه."""
    data.setdefault("providers", []).append({
        "name": name,
        "ipv4": ipv4 or [],
        "ipv6": ipv6 or [],
        "source": source,
    })
    return data
