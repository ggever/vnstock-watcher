from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

import autostart
import history
import updater
from config import AppConfig, SymbolConfig, load_config, save_config
from monitor import MonitorService
from notifier import WindowsNotifier
from version import __version__


class AppWindow(tk.Tk):
    def __init__(self, start_hidden: bool = False) -> None:
        super().__init__()
        self.title(f"VNStock Watcher {__version__}")
        self.geometry("980x640")
        self.minsize(860, 560)
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.config_data = load_config()
        self.tray_icon = None

        self.notifier = WindowsNotifier(on_error=lambda message: self.run_on_ui(lambda: self.append_log(message)))
        self.monitor = MonitorService(
            config_getter=self.current_config,
            notifier=self.notifier,
            on_status=lambda message: self.run_on_ui(lambda: self.status_var.set(message)),
            on_log=lambda message: self.run_on_ui(lambda: self.append_log(message)),
            on_history_updated=lambda: self.run_on_ui(self.refresh_history),
        )

        self._build_ui()
        self._load_config_into_ui()
        if not self.config_data.symbols:
            self.append_log("Chưa có mã. Thêm mã trong tab Cấu hình rồi nhấn Start.")
        self.refresh_history()
        self.after(1500, self.auto_check_update)

        if start_hidden:
            self.withdraw()

    def set_tray_icon(self, icon) -> None:
        self.tray_icon = icon

    def run_on_ui(self, func) -> None:
        self.after(0, func)

    def show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide(self) -> None:
        self.withdraw()

    def quit_app(self) -> None:
        self.monitor.stop()
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.destroy()

    def _build_ui(self) -> None:
        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.symbol_var = tk.StringVar()
        self.threshold_var = tk.StringVar()
        self.side_var = tk.StringVar(value="Cả hai")
        self.interval_var = tk.IntVar(value=10)
        self.auto_minimize_var = tk.BooleanVar(value=True)
        self.start_with_windows_var = tk.BooleanVar(value=False)
        self.history_symbol_var = tk.StringVar(value="ALL")
        self.history_date_var = tk.StringVar()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        config_tab = ttk.Frame(notebook, padding=10)
        history_tab = ttk.Frame(notebook, padding=10)
        notebook.add(config_tab, text="Cấu hình")
        notebook.add(history_tab, text="Lịch sử")

        self._build_config_tab(config_tab)
        self._build_history_tab(history_tab)

        status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status_bar.pack(fill="x", padx=10, pady=(0, 8))

    def _build_config_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(3, weight=1)

        form = ttk.Frame(parent)
        form.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Mã").grid(row=0, column=0, padx=(0, 6))
        ttk.Entry(form, textvariable=self.symbol_var, width=12).grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="Ngưỡng KL").grid(row=0, column=2, padx=(16, 6))
        ttk.Entry(form, textvariable=self.threshold_var, width=14).grid(row=0, column=3)
        ttk.Label(form, text="Chiều").grid(row=0, column=4, padx=(16, 6))
        ttk.Combobox(
            form,
            textvariable=self.side_var,
            values=("Cả hai", "Mua", "Bán"),
            width=8,
            state="readonly",
        ).grid(row=0, column=5)
        ttk.Button(form, text="Thêm/Sửa", command=self.add_or_update_symbol).grid(row=0, column=6, padx=(16, 0))
        ttk.Button(form, text="Xóa", command=self.remove_symbol).grid(row=0, column=7, padx=(6, 0))

        self.symbol_tree = ttk.Treeview(parent, columns=("symbol", "threshold", "side"), show="headings", height=8)
        self.symbol_tree.heading("symbol", text="Mã")
        self.symbol_tree.heading("threshold", text="Ngưỡng KL")
        self.symbol_tree.heading("side", text="Chiều")
        self.symbol_tree.column("symbol", width=120, anchor="center")
        self.symbol_tree.column("threshold", width=160, anchor="e")
        self.symbol_tree.column("side", width=120, anchor="center")
        self.symbol_tree.grid(row=1, column=0, sticky="nsew")
        symbol_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.symbol_tree.yview)
        self.symbol_tree.configure(yscrollcommand=symbol_scroll.set)
        symbol_scroll.grid(row=1, column=1, sticky="ns")
        self.symbol_tree.bind("<<TreeviewSelect>>", self._on_symbol_selected)

        controls = ttk.Frame(parent)
        controls.grid(row=2, column=0, sticky="ew", pady=10)
        ttk.Label(controls, text="Chu kỳ polling (giây)").pack(side="left")
        ttk.Spinbox(controls, from_=3, to=300, textvariable=self.interval_var, width=6).pack(side="left", padx=(6, 18))
        ttk.Checkbutton(
            controls,
            text="Tự thu vào tray khi Start",
            variable=self.auto_minimize_var,
        ).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(
            controls,
            text="Start cùng Windows",
            variable=self.start_with_windows_var,
        ).pack(side="left")
        ttk.Button(controls, text="Lưu cấu hình", command=self.save_settings).pack(side="right")
        ttk.Button(controls, text="Check for update", command=self.check_for_update).pack(side="right", padx=(0, 8))
        ttk.Button(controls, text="Stop", command=self.stop_monitoring).pack(side="right", padx=(0, 8))
        ttk.Button(controls, text="Start", command=self.start_monitoring).pack(side="right", padx=(0, 8))

        self.log_text = tk.Text(parent, height=10, wrap="word", state="disabled")
        self.log_text.grid(row=3, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=3, column=1, sticky="ns")

    def _build_history_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
        parent.rowconfigure(1, weight=1)

        filters = ttk.Frame(parent)
        filters.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(filters, text="Mã").pack(side="left")
        self.history_symbol_combo = ttk.Combobox(
            filters,
            textvariable=self.history_symbol_var,
            values=("ALL",),
            width=12,
            state="readonly",
        )
        self.history_symbol_combo.pack(side="left", padx=(6, 16))
        ttk.Label(filters, text="Từ ngày (YYYY-MM-DD)").pack(side="left")
        ttk.Entry(filters, textvariable=self.history_date_var, width=14).pack(side="left", padx=(6, 16))
        ttk.Button(filters, text="Lọc", command=self.refresh_history).pack(side="left")
        ttk.Button(filters, text="Xóa lịch sử", command=self.clear_history).pack(side="right")

        self.history_tree = ttk.Treeview(
            parent,
            columns=("time", "symbol", "side", "volume", "price", "value"),
            show="headings",
        )
        headings = {
            "time": "Time",
            "symbol": "Mã",
            "side": "Chiều",
            "volume": "KL",
            "price": "Giá",
            "value": "Giá trị",
        }
        for column, text in headings.items():
            self.history_tree.heading(column, text=text)
        self.history_tree.column("time", width=180)
        self.history_tree.column("symbol", width=80, anchor="center")
        self.history_tree.column("side", width=80, anchor="center")
        self.history_tree.column("volume", width=120, anchor="e")
        self.history_tree.column("price", width=120, anchor="e")
        self.history_tree.column("value", width=140, anchor="e")
        self.history_tree.tag_configure("mua", foreground="#007700")
        self.history_tree.tag_configure("ban", foreground="#cc0000")
        self.history_tree.grid(row=1, column=0, sticky="nsew")
        history_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scroll.set)
        history_scroll.grid(row=1, column=1, sticky="ns")

    def _load_config_into_ui(self) -> None:
        self.interval_var.set(self.config_data.interval)
        self.auto_minimize_var.set(self.config_data.auto_minimize_on_start)
        self.start_with_windows_var.set(self.config_data.start_with_windows)
        for symbol in self.config_data.symbols:
            self.symbol_tree.insert("", "end", iid=symbol.symbol, values=(symbol.symbol, symbol.threshold, symbol.side))

    def current_config(self) -> AppConfig:
        symbols = []
        for item_id in self.symbol_tree.get_children():
            symbol, threshold, side = self.symbol_tree.item(item_id, "values")
            symbols.append(SymbolConfig(symbol=str(symbol), threshold=int(threshold), side=str(side)))
        return AppConfig(
            interval=self._safe_interval(),
            auto_minimize_on_start=bool(self.auto_minimize_var.get()),
            start_with_windows=bool(self.start_with_windows_var.get()),
            last_update_check=self.config_data.last_update_check,
            symbols=symbols,
        )

    def add_or_update_symbol(self) -> None:
        symbol = self.symbol_var.get().strip().upper()
        if not symbol:
            messagebox.showwarning("Thiếu mã", "Vui lòng nhập mã chứng khoán.")
            return
        try:
            threshold = int(self.threshold_var.get())
        except ValueError:
            messagebox.showwarning("Sai ngưỡng", "Ngưỡng khối lượng phải là số nguyên.")
            return
        if threshold <= 0:
            messagebox.showwarning("Sai ngưỡng", "Ngưỡng khối lượng phải lớn hơn 0.")
            return
        side = self.side_var.get()
        if side not in {"Cả hai", "Mua", "Bán"}:
            side = "Cả hai"

        if self.symbol_tree.exists(symbol):
            self.symbol_tree.item(symbol, values=(symbol, threshold, side))
        else:
            self.symbol_tree.insert("", "end", iid=symbol, values=(symbol, threshold, side))
        self.save_settings(show_message=False)
        self._refresh_history_symbols()

    def remove_symbol(self) -> None:
        selection = self.symbol_tree.selection()
        if not selection:
            return
        for item_id in selection:
            self.symbol_tree.delete(item_id)
        self.save_settings(show_message=False)
        self._refresh_history_symbols()

    def save_settings(self, show_message: bool = True) -> None:
        self.config_data = self.current_config()
        save_config(self.config_data)
        self._sync_autostart()
        if show_message:
            messagebox.showinfo("Đã lưu", "Cấu hình đã được lưu.")

    def start_monitoring(self) -> None:
        self.save_settings(show_message=False)
        self.monitor.start()
        if self.auto_minimize_var.get():
            self.hide()

    def stop_monitoring(self) -> None:
        self.monitor.stop()

    def append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 500:
            self.log_text.delete("1.0", f"{line_count - 500}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def refresh_history(self) -> None:
        self._refresh_history_symbols()
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        rows = history.load_history(
            symbol_filter=self.history_symbol_var.get(),
            date_filter=self.history_date_var.get(),
            limit=500,
        )
        for index, row in enumerate(rows):
            side = _fmt_side(row.get("side", ""))
            tag = "mua" if side == "Mua" else ("ban" if side == "Bán" else "")
            self.history_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    row.get("time", ""),
                    row.get("symbol", ""),
                    side,
                    _fmt_number(row.get("volume")),
                    _fmt_number(row.get("price")),
                    _fmt_number(row.get("value")),
                ),
                tags=(tag,) if tag else (),
            )

    def clear_history(self) -> None:
        if messagebox.askyesno("Xóa lịch sử", "Bạn chắc chắn muốn xóa toàn bộ lịch sử?"):
            history.clear_history()
            self.refresh_history()

    def check_for_update(self) -> None:
        try:
            result = updater.check_update()
        except updater.UpdateUnavailable as exc:
            messagebox.showinfo("Update", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Update", f"Không kiểm tra được cập nhật: {exc}")
            return

        if result is None:
            messagebox.showinfo("Update", "Bạn đang dùng phiên bản mới nhất.")
            return

        version, url = result
        if messagebox.askyesno("Update", f"Có bản {version}. Tải về và khởi động lại?"):
            self._download_update(version, url)

    def auto_check_update(self) -> None:
        config = self.current_config()
        if not updater.should_auto_check(config):
            return

        try:
            result = updater.check_update()
            updater.mark_checked(config)
            self.config_data.last_update_check = config.last_update_check
        except Exception as exc:
            self.append_log(f"Không tự kiểm tra được update: {exc}")
            return

        if result is None:
            return

        version, _url = result
        self.notifier.notify(
            "Có bản cập nhật mới",
            f"VNStock Watcher {version} sẵn sàng. Mở app để cập nhật.",
        )
        self.append_log(f"Có bản cập nhật mới: {version}. Nhấn Check for update để cài.")

    def _download_update(self, version: str, url: str) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(f"Đang tải {version}")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        label_var = tk.StringVar(value="Đang tải bản cập nhật...")
        ttk.Label(dialog, textvariable=label_var, padding=(12, 12, 12, 6)).pack(fill="x")
        progress = ttk.Progressbar(dialog, mode="indeterminate", length=320)
        progress.pack(fill="x", padx=12, pady=(0, 12))
        progress.start(10)

        def on_progress(downloaded: int, total: int) -> None:
            def update_ui() -> None:
                if total <= 0:
                    label_var.set(f"Đã tải {downloaded // (1024 * 1024)} MB...")
                    return
                progress.stop()
                progress.configure(mode="determinate", maximum=total, value=downloaded)
                percent = downloaded / total * 100
                label_var.set(f"Đã tải {percent:.0f}%")

            self.run_on_ui(update_ui)

        def worker() -> None:
            try:
                updater.download_and_swap(url, progress_callback=on_progress)
            except Exception as exc:
                self.run_on_ui(lambda exc=exc: self._update_failed(dialog, exc))
                return
            self.run_on_ui(lambda: self._update_ready(dialog))

        threading.Thread(target=worker, name="VNStockUpdater", daemon=True).start()

    def _update_failed(self, dialog: tk.Toplevel, exc: Exception) -> None:
        if dialog.winfo_exists():
            dialog.destroy()
        messagebox.showerror("Update", f"Không cập nhật được: {exc}")

    def _update_ready(self, dialog: tk.Toplevel) -> None:
        if dialog.winfo_exists():
            dialog.destroy()
        self.quit_app()

    def _on_symbol_selected(self, _event=None) -> None:
        selection = self.symbol_tree.selection()
        if not selection:
            return
        values = self.symbol_tree.item(selection[0], "values")
        self.symbol_var.set(values[0])
        self.threshold_var.set(values[1])
        self.side_var.set(values[2])

    def _sync_autostart(self) -> None:
        try:
            if self.start_with_windows_var.get():
                autostart.enable()
            else:
                autostart.disable()
        except Exception as exc:
            self.start_with_windows_var.set(autostart.is_enabled())
            self.append_log(f"Không cập nhật được Start with Windows: {exc}")

    def _refresh_history_symbols(self) -> None:
        configured = [self.symbol_tree.item(item, "values")[0] for item in self.symbol_tree.get_children()]
        values = ["ALL"] + sorted(set(configured + history.distinct_symbols()))
        self.history_symbol_combo.configure(values=values)
        if self.history_symbol_var.get() not in values:
            self.history_symbol_var.set("ALL")

    def _safe_interval(self) -> int:
        try:
            return max(3, int(self.interval_var.get()))
        except (tk.TclError, ValueError):
            return 10


def _fmt_side(side: str) -> str:
    _MAP = {"BU": "Mua", "SD": "Bán", "Both": "Cả hai", "BOTH": "Cả hai"}
    return _MAP.get(side, side)


def _fmt_number(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"
