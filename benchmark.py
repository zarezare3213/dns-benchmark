"""
اجرای آزمایش کامل روی مجموعه‌ای از سرورهای DNS.
برای هر سرور: چند دامنهٔ آزمایشی و چند بار تکرار، سپس محاسبهٔ:
  - میانگین زمان پاسخ (ms)
  - انحراف‌معیار به‌عنوان شاخص پایداری/جیتر (ms)
  - درصد موفقیت
  - وضعیت نهایی: Up / Degraded / Down
"""

import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from core.resolver import measure_dns_query

DEFAULT_TEST_DOMAINS = [
    "example.com",
    "google.com",
    "cloudflare.com",
    "wikipedia.org",
]


@dataclass
class DnsServerResult:
    provider: str
    ip: str
    ip_version: str  # "IPv4" یا "IPv6"
    avg_time_ms: float | None = None
    jitter_ms: float | None = None
    success_rate: float = 0.0
    status: str = "نامشخص"
    total_queries: int = 0
    successful_queries: int = 0
    errors: list = field(default_factory=list)

    def to_row(self) -> dict:
        return {
            "provider": self.provider,
            "ip": self.ip,
            "ip_version": self.ip_version,
            "avg_time_ms": self.avg_time_ms,
            "jitter_ms": self.jitter_ms,
            "success_rate": self.success_rate,
            "status": self.status,
            "queries": f"{self.successful_queries}/{self.total_queries}",
        }


def _classify_status(success_rate: float, avg_time_ms: float | None) -> str:
    if success_rate == 0:
        return "قطع (Down)"
    if success_rate < 70 or avg_time_ms is None:
        return "ضعیف (Degraded)"
    if avg_time_ms > 300:
        return "کند (Slow)"
    return "پایدار (Up)"


def benchmark_single_server(provider: str, ip: str, ip_version: str,
                             test_domains: list[str], repeats: int = 3,
                             timeout: float = 3.0) -> DnsServerResult:
    """اجرای repeats بار پرس‌وجو برای هر دامنه، روی یک سرور DNS واحد."""
    result = DnsServerResult(provider=provider, ip=ip, ip_version=ip_version)
    times = []

    for domain in test_domains:
        for _ in range(repeats):
            outcome = measure_dns_query(ip, domain, timeout=timeout)
            result.total_queries += 1
            if outcome["success"]:
                result.successful_queries += 1
                times.append(outcome["time_ms"])
            else:
                result.errors.append(f"{domain}: {outcome['error']}")

    if times:
        result.avg_time_ms = round(statistics.mean(times), 2)
        result.jitter_ms = round(statistics.pstdev(times), 2) if len(times) > 1 else 0.0

    result.success_rate = round(
        (result.successful_queries / result.total_queries) * 100, 1
    ) if result.total_queries else 0.0

    result.status = _classify_status(result.success_rate, result.avg_time_ms)
    return result


def run_full_benchmark(servers: list[dict], test_domains: list[str] | None = None,
                        repeats: int = 3, timeout: float = 3.0,
                        max_workers: int = 8, progress_callback=None) -> list[DnsServerResult]:
    """servers: لیستی از dict با کلیدهای provider, ip, ip_version
    progress_callback(done, total) در صورت تمایل برای به‌روزرسانی نوار پیشرفت GUI."""
    domains = test_domains or DEFAULT_TEST_DOMAINS
    results = []
    total = len(servers)
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                benchmark_single_server, s["provider"], s["ip"], s["ip_version"],
                domains, repeats, timeout
            ): s
            for s in servers
        }
        for future in as_completed(futures):
            results.append(future.result())
            done += 1
            if progress_callback:
                progress_callback(done, total)

    # پایدارترین و سریع‌ترین‌ها بالا؛ خطاداده‌ها پایین
    results.sort(key=lambda r: (
        0 if r.success_rate > 0 else 1,
        -r.success_rate,
        r.avg_time_ms if r.avg_time_ms is not None else float("inf"),
    ))
    return results
