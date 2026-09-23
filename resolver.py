"""
اندازه‌گیری پاسخ‌دهی یک سرور DNS مشخص برای یک دامنهٔ آزمایشی.
از کتابخانهٔ dnspython استفاده می‌کند تا پرس‌وجو مستقیماً به IP سرور DNS
مورد نظر ارسال شود (بدون تغییر تنظیمات DNS سیستم).
"""

import time
import dns.resolver
import dns.exception


def measure_dns_query(server_ip: str, domain: str, timeout: float = 3.0,
                       record_type: str = "A") -> dict:
    """یک پرس‌وجوی DNS واحد را اجرا و نتیجه را برمی‌گرداند.

    خروجی:
        {
          "success": bool,
          "time_ms": float | None,
          "answers": list[str] | None,
          "error": str | None,
        }
    """
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [server_ip]
    resolver.timeout = timeout
    resolver.lifetime = timeout

    start = time.perf_counter()
    try:
        answer = resolver.resolve(domain, record_type, raise_on_no_answer=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "success": True,
            "time_ms": round(elapsed_ms, 2),
            "answers": [str(r) for r in answer],
            "error": None,
        }
    except dns.exception.Timeout:
        return {"success": False, "time_ms": None, "answers": None, "error": "timeout"}
    except dns.resolver.NXDOMAIN:
        return {"success": False, "time_ms": None, "answers": None, "error": "nxdomain"}
    except dns.resolver.NoAnswer:
        return {"success": False, "time_ms": None, "answers": None, "error": "no_answer"}
    except dns.resolver.NoNameservers:
        return {"success": False, "time_ms": None, "answers": None, "error": "no_nameservers"}
    except Exception as exc:  # noqa: BLE001 - می‌خواهیم هر خطایی گزارش شود، نه کرش کند
        return {"success": False, "time_ms": None, "answers": None, "error": str(exc)}


def check_tcp_reachability(ip: str, port: int = 53, timeout: float = 2.0) -> bool:
    """بررسی می‌کند آیا می‌توان یک اتصال TCP ساده به سرور DNS برقرار کرد.
    این فقط «در دسترس بودن پورت سرویس DNS» را می‌سنجد، نه محتوای سایت‌ها."""
    import socket
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False
