# Improvement Notes — VNStock Big-Order Watcher

Code review của `src/`. Đã điều chỉnh lại theo feedback review lần 2 — chia thành Batch 1 (làm ngay), Deferred (cần cân nhắc thêm), và v1.1 Backlog.

---

## Batch 1 — Implement ngay

Các fix gọn, ít rủi ro, impact rõ ràng. Không thay đổi kiến trúc hay quyết định trong PLAN.md.

---

### 1. CSV race condition — `history.py` *(High)*

`append_rows()` gọi từ monitor thread, `load_history()` / `distinct_symbols()` / `clear_history()` gọi từ UI thread. Không có lock bảo vệ file.

**Fix:** thêm module-level `threading.Lock`, acquire trong cả 4 hàm:

```python
_csv_lock = threading.Lock()

def append_rows(symbol, rows):
    with _csv_lock:
        ...  # logic không đổi

def load_history(...):
    with _csv_lock:
        ...

def clear_history():
    with _csv_lock:
        ...

def distinct_symbols():
    with _csv_lock:
        ...
```

> *Note:* severity là High chứ không phải Critical — fix lock là đủ cho v1, chưa cần rewrite storage. Race thực tế hiếm (clear và write khó trùng đúng millisecond), nhưng nên fix trước khi ship.

---

### 2. Partial download left on disk — `updater.py:68-74` *(High)*

Download thất bại giữa chừng (mất mạng, timeout) để lại file `.exe.new` trên disk mãi mãi.

**Fix:** wrap try/finally để dọn file lỗi:

```python
try:
    with requests.get(url, stream=True, timeout=30) as response:
        response.raise_for_status()
        with new_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=512 * 1024):
                if chunk:
                    handle.write(chunk)
except Exception:
    if new_path.exists():
        new_path.unlink()
    raise
```

---

### 3. `page_size=100` có thể bỏ sót tick — `monitor.py:118` *(High)*

Mã active (VNM, HPG) với polling interval dài (60s) dễ vượt 100 tick/chu kỳ — lệnh lớn bị bỏ qua âm thầm.

**Fix:** tính động theo interval:

```python
page_size = max(100, int(config.interval) * 10)
frame = quote.intraday(page_size=page_size)
```

---

### 4. Unbounded `log_text` — `gui.py:140` *(High)*

Chạy cả ngày (6h × 360 polls × N mã) → hàng nghìn dòng log tích lũy trong RAM.

**Fix:** giới hạn 500 dòng sau mỗi append:

```python
def append_log(self, message: str) -> None:
    self.log_text.configure(state="normal")
    self.log_text.insert("end", f"{message}\n")
    line_count = int(self.log_text.index("end-1c").split(".")[0])
    if line_count > 500:
        self.log_text.delete("1.0", f"{line_count - 500}.0")
    self.log_text.see("end")
    self.log_text.configure(state="disabled")
```

---

### 5. Missing scrollbars — `gui.py:111`, `gui.py:140` *(High)*

`symbol_tree` (height=8) và `log_text` không có scrollbar widget — thêm >8 mã thì tree không scroll được bằng chuột.

**Fix:** gắn `ttk.Scrollbar` vào cả hai:

```python
# symbol_tree
scroll = ttk.Scrollbar(parent, orient="vertical", command=self.symbol_tree.yview)
self.symbol_tree.configure(yscrollcommand=scroll.set)
self.symbol_tree.grid(row=1, column=0, sticky="nsew")
scroll.grid(row=1, column=1, sticky="ns")

# log_text — tương tự
scroll = ttk.Scrollbar(parent, orient="vertical", command=self.log_text.yview)
self.log_text.configure(yscrollcommand=scroll.set)
```

Điều chỉnh `columnconfigure` cho column mới của scrollbar.

---

### 6. `data_dir()` dùng `cwd` trong dev — `paths.py:10` *(Medium)*

```python
return Path.cwd()
```

Chạy `python src/main.py` từ thư mục khác project root → `config.json` và `history.csv` sinh ra nhầm chỗ.

**Fix:** anchor về project root:

```python
def data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # src/../
```

---

### 7. Default config có mã ví dụ hardcoded — `config.py:36-44` *(Medium)*

User mới thấy VNM + FPT pre-populated, có thể nhầm tưởng đã cấu hình xong mà threshold không đúng.

**Fix:** default symbols rỗng, thêm hint log khi start:

```python
def default_config() -> AppConfig:
    return AppConfig(interval=10, symbols=[])
```

Trong `monitor.py` khi `config.symbols` rỗng, log: _"Chưa có mã. Thêm mã trong tab Cấu hình."_

---

### 8. `autostart.enable()` raise trong dev mode — `autostart.py:21-23` *(Medium)*

Tick checkbox "Start cùng Windows" khi đang dev sẽ raise `RuntimeError`, checkbox snaps back `False` và log lỗi gây khó hiểu.

**Fix:** silent no-op khi không phải exe:

```python
def enable() -> None:
    if not getattr(sys, "frozen", False):
        return  # shortcut chỉ có nghĩa với .exe build
    ...
```

---

### 9. `build.bat` — không có venv, không check Python version *(Medium)*

Install deps global có thể conflict. Python <3.9 fail với error khó hiểu về type hints.

**Fix:**

```bat
python --version 2>&1 | findstr /r "3\.[91][0-9]*" > nul
if errorlevel 1 (
    echo Yeu cau Python 3.9+. Vui long cai Python truoc.
    exit /b 1
)

if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller ...
```

---

## Deferred — Cần cân nhắc thêm

Các issue đúng về kỹ thuật nhưng phức tạp hơn, hoặc thay đổi hành vi đã quyết định trong PLAN.md.

---

### 10. Notification cooldown per symbol — `monitor.py` *(Deferred)*

Với `interval=3s`, có thể spam toast liên tục cho 1 mã active.

**Vấn đề với fix đơn giản:** hardcode `MIN_NOTIFY_GAP = 30s` thay đổi quyết định trong PLAN.md ("1 toast / mã / chu kỳ"). Nếu user set interval=60s, cooldown 30s vô nghĩa; nếu interval=3s, 30s có thể bỏ lỡ tín hiệu quan trọng.

**Hướng làm đúng:** thêm field `notify_cooldown_seconds` vào `SymbolConfig` hoặc `AppConfig` (default 0 = tắt), expose trong GUI. History và log vẫn ghi đầy đủ — chỉ toast bị throttle.

---

### 11. API error backoff — `monitor.py:112-113` *(Deferred)*

Khi VCI API lỗi liên tiếp, hiện tại retry ngay sau `interval` giây — có thể hammer API.

**Vấn đề với fix gợi ý cũ:** `self._stop_event.wait(300)` trong `_poll_symbol` block toàn bộ loop, kể cả các mã khác đang healthy.

**Hướng làm đúng:** dùng `_next_retry_at: dict[str, datetime]` per-symbol:

```python
# trong _poll_symbol khi catch exception:
fail_count = self._fail_count.get(symbol, 0) + 1
self._fail_count[symbol] = fail_count
if fail_count >= 5:
    self._next_retry_at[symbol] = datetime.now() + timedelta(minutes=5)
    self.on_log(f"{symbol}: lỗi {fail_count} lần liên tiếp, tạm dừng 5 phút.")

# ở đầu _poll_symbol:
retry_at = self._next_retry_at.get(symbol)
if retry_at and datetime.now() < retry_at:
    return  # skip, không block mã khác
```

---

### 12. Download progress — `updater.py` *(Deferred)*

~100MB download không có feedback — UI có vẻ đơ.

**Lý do hoãn:** auto-update hiện disabled (`GITHUB_REPO = None`). Implement progress dialog trước khi có repo là over-engineering. Làm khi bật auto-update thật.

---

### 13. HNX afternoon close 14:45 — `market_hours.py` *(Deferred)*

HNX đóng continuous trading lúc 14:45 thay vì 15:00 như HoSE.

**Lý do hoãn:** cần xác minh đúng giờ từng sàn theo từng loại phiên (ATO/ATC/continuous), và biết user đang monitor HoSE hay HNX. Nếu làm, nên là feature riêng với `exchange` field trong `SymbolConfig`. Hiện tại giữ HoSE default là đủ.

---

## v1.1 Backlog

Làm sau khi v1 ổn định, nếu cần thiết.

---

### 14. Migrate CSV → SQLite *(v1.1)*

Giải quyết triệt để race condition (#1), `distinct_symbols()` scan toàn file (#15), và load_history RAM usage. Không tăng kích thước exe (sqlite3 là stdlib).

**Chỉ implement khi:** history.csv bắt đầu lớn (>50k rows) hoặc race condition xảy ra thực tế dù đã có lock. Chi tiết implementation — xem [plan đã thiết kế trước đó](#migration-plan-csv--sqlite-srchistorypy).

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
    volume INTEGER NOT NULL, price REAL NOT NULL, value REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_symbol_time ON orders (symbol, time);
```

Thread safety: WAL mode + new connection per call (không cần Lock thủ công).
Auto-migration: nếu `history.csv` tồn tại khi khởi động lần đầu → import → rename sang `.csv.bak`.

---

### 15. `distinct_symbols()` scan toàn file — `history.py:79-81` *(v1.1)*

Hiện load 100k rows chỉ để lấy danh sách mã. Fix nhanh là scan chỉ cột `symbol`:

```python
def distinct_symbols() -> list[str]:
    path = history_path()
    if not path.exists():
        return []
    symbols: set[str] = set()
    with _csv_lock, path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            sym = row.get("symbol", "").strip().upper()
            if sym:
                symbols.add(sym)
    return sorted(symbols)
```

Nếu upgrade SQLite thì dùng `SELECT DISTINCT symbol` thay thế.

---

### 16. CSV size cap / rotation *(v1.1)*

Threshold thấp có thể sinh hàng triệu rows. Thêm tùy chọn "Xóa lịch sử trước ngày..." trong GUI, hoặc auto-cap 100k rows (drop oldest).

---

## Minor / Polish (bất cứ lúc nào)

| # | File | Mô tả |
|---|------|--------|
| 17 | `notifier.py:29` | Silent `except Exception` — nên log lỗi toast vào GUI thay vì bỏ qua hoàn toàn |
| 18 | `monitor.py:63` | `max(3, int(config.interval or 10))` thừa vì `parse_config` đã clamp — xóa đi |
| 19 | `tray.py` | Thêm `pystray.Menu.SEPARATOR` giữa Start/Stop và Thoát để tránh mis-click |

---

## Summary table

| # | File | Batch | Severity |
|---|------|-------|----------|
| 1 | `history.py` | Batch 1 | High — CSV lock |
| 2 | `updater.py` | Batch 1 | High — cleanup .exe.new |
| 3 | `monitor.py` | Batch 1 | High — dynamic page_size |
| 4 | `gui.py` | Batch 1 | High — trim log 500 lines |
| 5 | `gui.py` | Batch 1 | High — scrollbars |
| 6 | `paths.py` | Batch 1 | Medium — dev data_dir root |
| 7 | `config.py` | Batch 1 | Medium — empty default symbols |
| 8 | `autostart.py` | Batch 1 | Medium — no-op in dev |
| 9 | `build.bat` | Batch 1 | Medium — venv + Python guard |
| 10 | `monitor.py` | Deferred | — notification cooldown (configurable) |
| 11 | `monitor.py` | Deferred | — per-symbol retry backoff |
| 12 | `updater.py` | Deferred | — download progress (setelah GitHub repo live) |
| 13 | `market_hours.py` | Deferred | — HNX hours (needs exchange-aware design) |
| 14 | `history.py` | v1.1 | — SQLite migration |
| 15 | `history.py` | v1.1 | — distinct_symbols column-scan |
| 16 | `history.py` | v1.1 | — CSV rotation |
| 17 | `notifier.py` | Polish | — log toast failures |
| 18 | `monitor.py` | Polish | — remove redundant interval guard |
| 19 | `tray.py` | Polish | — menu separator |
