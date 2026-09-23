"""
رابط گرافیکی مدرن (Tkinter + تم sv_ttk).

اگر پکیج sv_ttk نصب نباشد، برنامه بدون کرش با تم پیش‌فرض ادامه می‌دهد
(fallback امن) — یعنی وابستگی سخت به یک کتابخانهٔ ظاهری ایجاد نمی‌شود.

امکانات:
  - هدر برند‌دار + نوار وضعیت با پیشرفت زنده
  - کارت‌های خلاصهٔ آماری (تعداد سرور، پایدارترین، سریع‌ترین)
  - جدول با رنگ‌بندی وضعیت (سبز/زرد/قرمز)
  - جست‌وجو، فیلتر وضعیت، مرتب‌سازی با کلیک ستون
  - ویرایش دامنه‌های آزمایشی
  - اجرای دوبارهٔ تست‌ها با نوار پیشرفت
  - اعمال DNS انتخابی روی آداپتور شبکه — فقط با تأیید صریح کاربر
"""

import platform
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from core.benchmark import run_full_benchmark, DEFAULT_TEST_DOMAINS
from core.updater import load_providers, flatten_to_server_list

try:
    import sv_ttk
    _HAS_SV_TTK = True
except ImportError:
    _HAS_SV_TTK = False

COLUMNS = [
    ("provider", "سرویس‌دهنده", 190),
    ("ip", "آدرس IP", 160),
    ("ip_version", "نسخه", 60),
    ("avg_time_ms", "میانگین (ms)", 100),
    ("jitter_ms", "جیتر (ms)", 90),
    ("success_rate", "موفقیت (%)", 90),
    ("status", "وضعیت", 130),
    ("queries", "پرس‌وجوها", 90),
]

STATUS_FILTERS = ["همه", "پایدار (Up)", "کند (Slow)", "ضعیف (Degraded)", "قطع (Down)"]

PALETTE = {
    "bg": "#0f1420",
    "panel": "#161d2e",
    "accent": "#5b8cff",
    "accent_soft": "#233252",
    "text": "#e8ecf7",
    "muted": "#8b93a8",
    "up": "#2fbf71",
    "slow": "#e0a72e",
    "degraded": "#e0752e",
    "down": "#e5484d",
}

STATUS_TAG = {
    "پایدار (Up)": "row_up",
    "کند (Slow)": "row_slow",
    "ضعیف (Degraded)": "row_degraded",
    "قطع (Down)": "row_down",
}


class DnsBenchmarkApp:
    def __init__(self, root: tk.Tk, providers_path: str):
        self.root = root
        self.providers_path = providers_path
        self.test_domains = list(DEFAULT_TEST_DOMAINS)
        self.all_results = []
        self.sort_state = {"column": None, "reverse": False}

        root.title("ابزار سنجش سرعت و پایداری DNS عمومی")
        root.geometry("1060x620")
        root.minsize(860, 500)

        self._apply_theme()
        self._build_header()
        self._build_toolbar()
        self._build_summary_cards()
        self._build_table()
        self._build_statusbar()

    # ---------- تم و ظاهر ----------

    def _apply_theme(self):
        if _HAS_SV_TTK:
            sv_ttk.set_theme("dark")
        self.root.configure(bg=PALETTE["bg"])

        style = ttk.Style()
        style.configure("Header.TFrame", background=PALETTE["bg"])
        style.configure("Card.TFrame", background=PALETTE["panel"])
        style.configure("Title.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"],
                         font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"],
                         font=("Segoe UI", 10))
        style.configure("CardValue.TLabel", background=PALETTE["panel"], foreground=PALETTE["accent"],
                         font=("Segoe UI", 20, "bold"))
        style.configure("CardLabel.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"],
                         font=("Segoe UI", 9))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    # ---------- ساخت اجزا ----------

    def _build_header(self):
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(20, 16, 20, 8))
        header.pack(fill="x")
        ttk.Label(header, text="🌐 سنجش سرعت و پایداری DNSهای عمومی",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(header,
                  text="مقایسهٔ زمان پاسخ، جیتر و درصد موفقیت سرویس‌دهنده‌های شناخته‌شدهٔ DNS",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(20, 4, 20, 8))
        bar.pack(fill="x")

        ttk.Label(bar, text="جست‌وجو:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filters())
        ttk.Entry(bar, textvariable=self.search_var, width=20).pack(side="left", padx=(6, 16))

        ttk.Label(bar, text="فیلتر وضعیت:").pack(side="left")
        self.status_var = tk.StringVar(value=STATUS_FILTERS[0])
        status_combo = ttk.Combobox(bar, textvariable=self.status_var, values=STATUS_FILTERS,
                                     state="readonly", width=16)
        status_combo.pack(side="left", padx=(6, 16))
        status_combo.bind("<<ComboboxSelected>>", lambda *_: self._apply_filters())

        ttk.Button(bar, text="✏️ دامنه‌های آزمایشی",
                   command=self._edit_domains).pack(side="left", padx=(0, 8))

        self.run_btn = ttk.Button(bar, text="▶ اجرای تست", style="Accent.TButton",
                                   command=self._start_benchmark)
        self.run_btn.pack(side="left", padx=(0, 8))

        ttk.Button(bar, text="⚙ اعمال DNS انتخابی…",
                   command=self._apply_selected_dns).pack(side="left")

        self.progress = ttk.Progressbar(bar, mode="determinate", length=160)
        self.progress.pack(side="right", padx=(0, 4))

    def _build_summary_cards(self):
        wrap = ttk.Frame(self.root, padding=(20, 0, 20, 10))
        wrap.pack(fill="x")

        self.card_total = self._make_card(wrap, "تعداد سرور تست‌شده", "—")
        self.card_stable = self._make_card(wrap, "پایدارترین سرویس‌دهنده", "—")
        self.card_fastest = self._make_card(wrap, "سریع‌ترین میانگین پاسخ", "—")
        for card in (self.card_total, self.card_stable, self.card_fastest):
            card["frame"].pack(side="left", expand=True, fill="both", padx=(0, 10))

    def _make_card(self, parent, label, value):
        frame = ttk.Frame(parent, style="Card.TFrame", padding=14)
        value_lbl = ttk.Label(frame, text=value, style="CardValue.TLabel")
        value_lbl.pack(anchor="w")
        ttk.Label(frame, text=label, style="CardLabel.TLabel").pack(anchor="w", pady=(2, 0))
        return {"frame": frame, "value_label": value_lbl}

    def _build_table(self):
        frame = ttk.Frame(self.root, padding=(20, 0, 20, 8))
        frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(frame, columns=[c[0] for c in COLUMNS], show="headings")
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label, command=lambda k=key: self._sort_by(k))
            self.tree.column(key, width=width, anchor="center")

        self.tree.tag_configure("row_up", foreground=PALETTE["up"])
        self.tree.tag_configure("row_slow", foreground=PALETTE["slow"])
        self.tree.tag_configure("row_degraded", foreground=PALETTE["degraded"])
        self.tree.tag_configure("row_down", foreground=PALETTE["down"])

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_statusbar(self):
        self.status_label = ttk.Label(self.root, text="آماده", anchor="w", padding=(20, 6))
        self.status_label.pack(fill="x", side="bottom")

    # ---------- منطق ----------

    def _edit_domains(self):
        current = ", ".join(self.test_domains)
        new_value = simpledialog.askstring(
            "دامنه‌های آزمایشی",
            "دامنه‌ها را با کاما جدا کنید:",
            initialvalue=current,
        )
        if new_value:
            domains = [d.strip() for d in new_value.split(",") if d.strip()]
            if domains:
                self.test_domains = domains

    def _start_benchmark(self):
        self.run_btn.state(["disabled"])
        self.progress["value"] = 0
        self.status_label.config(text="در حال اجرای آزمایش…")
        threading.Thread(target=self._run_benchmark_thread, daemon=True).start()

    def _run_benchmark_thread(self):
        try:
            data = load_providers(self.providers_path)
            servers = flatten_to_server_list(data)
            self.progress["maximum"] = len(servers)
            results = run_full_benchmark(
                servers,
                test_domains=self.test_domains,
                repeats=3,
                progress_callback=self._on_progress,
            )
            self.all_results = results
            self.root.after(0, self._apply_filters)
            self.root.after(0, self._update_summary_cards)
            self.root.after(0, lambda: self.status_label.config(
                text=f"پایان آزمایش — {len(results)} سرور بررسی شد."))
        except Exception as exc:  # noqa: BLE001
            self.root.after(0, lambda: messagebox.showerror("خطا", str(exc)))
        finally:
            self.root.after(0, lambda: self.run_btn.state(["!disabled"]))

    def _on_progress(self, done, total):
        def update():
            self.progress["value"] = done
            self.status_label.config(text=f"در حال آزمایش… ({done}/{total})")
        self.root.after(0, update)

    def _update_summary_cards(self):
        results = self.all_results
        self.card_total["value_label"].config(text=str(len(results)))

        stable = [r for r in results if r.status == "پایدار (Up)"]
        if stable:
            best_stable = min(stable, key=lambda r: r.jitter_ms if r.jitter_ms is not None else float("inf"))
            self.card_stable["value_label"].config(text=best_stable.provider)
        else:
            self.card_stable["value_label"].config(text="—")

        with_time = [r for r in results if r.avg_time_ms is not None]
        if with_time:
            fastest = min(with_time, key=lambda r: r.avg_time_ms)
            self.card_fastest["value_label"].config(
                text=f"{fastest.provider} ({fastest.avg_time_ms} ms)")
        else:
            self.card_fastest["value_label"].config(text="—")

    def _apply_filters(self):
        query = self.search_var.get().strip().lower()
        status_filter = self.status_var.get()

        rows = self.all_results
        if query:
            rows = [r for r in rows if query in r.provider.lower() or query in r.ip]
        if status_filter != "همه":
            rows = [r for r in rows if r.status == status_filter]

        self.tree.delete(*self.tree.get_children())
        for r in rows:
            row = r.to_row()
            values = [row[c[0]] if row[c[0]] is not None else "-" for c in COLUMNS]
            tag = STATUS_TAG.get(r.status, "")
            self.tree.insert("", "end", values=values, tags=(tag,) if tag else ())

    def _sort_by(self, column):
        reverse = self.sort_state["column"] == column and not self.sort_state["reverse"]
        self.sort_state = {"column": column, "reverse": reverse}

        def key_fn(r):
            val = r.to_row()[column]
            return (val is None, val)

        self.all_results.sort(key=key_fn, reverse=reverse)
        self._apply_filters()

    def _apply_selected_dns(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("انتخاب نشده", "لطفاً ابتدا یک ردیف از جدول را انتخاب کنید.")
            return
        values = self.tree.item(selection[0], "values")
        provider, ip = values[0], values[1]

        if platform.system() != "Windows":
            messagebox.showwarning("غیرقابل اجرا",
                                    "اعمال خودکار DNS فقط روی ویندوز پیاده‌سازی شده است.")
            return

        confirmed = messagebox.askyesno(
            "تأیید تغییر تنظیمات شبکه",
            f"آیا مطمئن هستید می‌خواهید DNS اصلی سیستم به‌صورت دستی به\n"
            f"{provider} ({ip})\nتغییر کند؟\n\n"
            "این کار نیازمند اجرای برنامه با دسترسی Administrator است و "
            "تنظیمات فعلی آداپتور شبکهٔ فعال را بازنویسی می‌کند."
        )
        if not confirmed:
            return

        adapter = simpledialog.askstring(
            "نام آداپتور شبکه",
            "نام دقیق آداپتور شبکه را وارد کنید (مثلاً Ethernet یا Wi-Fi):",
        )
        if not adapter:
            return

        try:
            subprocess.run(
                ["netsh", "interface", "ip", "set", "dns", f"name={adapter}",
                 "static", ip, "primary"],
                check=True, capture_output=True, text=True,
            )
            messagebox.showinfo("انجام شد", f"DNS آداپتور «{adapter}» به {ip} تغییر کرد.")
        except subprocess.CalledProcessError as exc:
            messagebox.showerror(
                "خطا",
                "تغییر DNS ناموفق بود. برنامه را با دسترسی Administrator اجرا کنید.\n\n"
                f"جزئیات: {exc.stderr}",
            )


def launch(providers_path: str = "dns_providers.json"):
    root = tk.Tk()
    DnsBenchmarkApp(root, providers_path)
    root.mainloop()
