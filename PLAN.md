# Plan: VNStock Big-Order Notifier (Windows Desktop App)

## Context

User cần một app desktop Windows theo dõi **lệnh khớp lớn** (big trades) của một hoặc nhiều mã chứng khoán Việt Nam theo thời gian thực. Khi có lệnh khớp với khối lượng vượt ngưỡng do user cấu hình, app hiển thị Windows toast notification để user chú ý (tín hiệu dòng tiền lớn vào/ra).

**Môi trường target:** máy Windows của user **không có Python sẵn** → đóng gói thành 1 file `.exe` standalone (PyInstaller).

**Dữ liệu:** dùng [`vnstock`](https://github.com/thinh-vu/vnstock) — API `Quote.intraday()` trả về tick (price, volume, time, match_type BU/SD).

---

## Decisions (đã chốt với user)

| Mục | Lựa chọn |
|---|---|
| Loại dữ liệu | Lệnh khớp intraday (`Quote.intraday()`) |
| Đóng gói | PyInstaller → 1 file `.exe` standalone |
| Cấu hình | GUI Tkinter (list mã + Start/Stop) |
| Số mã | Nhiều mã, threshold riêng từng mã |
| Đơn vị threshold | Khối lượng khớp (số cổ phiếu) |
| Giờ chạy | Chỉ trong giờ giao dịch (9:00–11:30 & 13:00–15:00, T2–T6) |
| Filter chiều lệnh | User chọn BU/SD/Both per mã |
| Notification | Gộp theo chu kỳ polling (1 toast / mã / chu kỳ nếu có ≥1 lệnh lớn) |
| History | CSV cạnh exe + tab "Lịch sử" trong GUI có filter |
| Auto-update | GitHub Releases (cần repo public) |
| System tray | Đóng = thu vào tray, tùy chọn auto-minimize khi Start, tùy chọn Start with Windows |

---

## Tech Stack

- **Python 3.11**
- **vnstock** — fetch intraday ticks
- **tkinter** + **ttk** (built-in) — GUI (Treeview cho history table)
- **winotify** — Windows 10/11 toast notification
- **pystray** + **Pillow** — system tray icon + menu
- **requests** — auto-update HTTP calls (GitHub API + download .exe)
- **packaging** — so sánh semver versions
- **pytz** — giờ giao dịch VN
- **pywin32** — tạo shortcut .lnk cho Start with Windows
- **threading** — polling thread tách GUI thread

---

## Project Structure

```
chungkhoan/
├── src/
│   ├── main.py              # entry: load config → tray + GUI
│   ├── gui.py               # Tkinter: 2 tab (Config | Lịch sử), Start/Stop
│   ├── monitor.py           # Polling thread: fetch + threshold + dedup + ghi history
│   ├── notifier.py          # winotify wrapper
│   ├── market_hours.py      # is_trading_time() VN
│   ├── tray.py              # pystray: icon, menu Show/Start/Stop/Quit
│   ├── updater.py           # GitHub Releases check + download + swap
│   ├── history.py           # append CSV, query/filter cho GUI
│   ├── autostart.py         # tạo/xóa shortcut trong Windows startup folder
│   ├── config.py            # load/save config.json
│   └── version.py           # __version__ = "1.0.0"
├── assets/
│   └── icon.ico             # icon cho exe & tray
├── config.json              # persist (sinh ra cạnh exe)
├── history.csv              # sinh ra cạnh exe
├── requirements.txt
├── build.bat
└── README.md
```

**Đường dẫn data files (`config.json`, `history.csv`):** `Path(sys.executable).parent` khi chạy exe; `Path.cwd()` khi chạy dev.

---

## Component Details

### `monitor.py` — polling loop (thread riêng)

```
for tick in interval (default 10s):
    if not is_trading_time():
        gui.set_status("Thị trường đóng cửa")
        sleep(60); continue

    for sym in config.symbols:
        df = Quote(sym.code, source='VCI').intraday(page_size=100)
        new = df[df['time'] > last_seen[sym.code]]
        last_seen[sym.code] = df['time'].max()

        if first_poll[sym.code]:        # bỏ qua history khi vừa Start
            first_poll[sym.code] = False
            continue

        big = new[(new['volume'] >= sym.threshold) &
                  side_match(new['match_type'], sym.side)]
        if not big.empty:
            notifier.notify_big_order(sym.code, big)
            history.append_rows(sym.code, big)     # ghi CSV
            gui.append_log(...)
            gui.refresh_history_if_visible()
```

### `history.py`

```python
HEADERS = ["time", "symbol", "side", "volume", "price", "value"]

def append_rows(symbol, df):
    path = data_dir() / "history.csv"
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file: w.writerow(HEADERS)
        for _, r in df.iterrows():
            w.writerow([r['time'], symbol, r['match_type'],
                        r['volume'], r['price'], r['volume']*r['price']])

def load(symbol_filter=None, date_filter=None, limit=500):
    # đọc CSV → list dict, apply filter, return cho GUI Treeview
    ...
```

> *Trade-off:* CSV không có index → load filter nhẹ trong RAM. OK đến ~100k dòng. Nếu lớn hơn, sau này upgrade SQLite.

### `gui.py` — 2 tab

**Tab 1: Config** — bảng mã/threshold/side, Start/Stop, log realtime, status. Thêm:
- ☑ Tự động minimize về tray khi Start
- ☑ Start cùng Windows
- 🔄 Check for update (button)

**Tab 2: Lịch sử**
```
┌─ Filter ───────────────────────────────┐
│ Mã: [VNM ▾]  Từ ngày: [____]  [Lọc]   │
│                          [Xóa lịch sử] │
├────────────────────────────────────────┤
│ Time      Mã   Chiều  KL      Giá      │
│ 14:23:05  VNM  BU     15,000  72,500   │
│ 14:22:50  VNM  SD     12,000  72,400   │
│ ...                                    │
└────────────────────────────────────────┘
```
- ttk.Treeview, load max 500 dòng gần nhất theo filter
- "Xóa lịch sử" có confirm dialog

### `tray.py` — pystray

```python
def build_tray(gui, monitor):
    menu = pystray.Menu(
        item("Hiện cửa sổ", lambda: gui.show()),
        item("Start", lambda: monitor.start(), enabled=lambda i: not monitor.running),
        item("Stop",  lambda: monitor.stop(),  enabled=lambda i: monitor.running),
        item("Thoát", lambda: app.quit()),
    )
    icon = pystray.Icon("VNStockWatcher", load_icon(), "VNStock Watcher", menu)
    icon.run_detached()
```

- Window close (X) → `gui.withdraw()` (ẩn) thay vì destroy. Chỉ "Thoát" menu mới kết thúc tiến trình.
- Khi `monitor.start()` được trigger và config "auto minimize" bật → `gui.withdraw()` ngay.

### `updater.py` — GitHub Releases

```python
GITHUB_REPO = "<owner>/<repo>"   # user điền sau

def check_update():
    r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                     timeout=10)
    latest = Version(r.json()["tag_name"].lstrip("v"))
    current = Version(__version__)
    if latest > current:
        asset = next(a for a in r.json()["assets"]
                     if a["name"].endswith(".exe"))
        return latest, asset["browser_download_url"]
    return None

def download_and_swap(url):
    # 1. Tải về <exe>.new
    # 2. Viết updater.bat: chờ exe cũ thoát, rename .new → .exe, restart
    # 3. Chạy updater.bat detached, app tự thoát
```

**Flow user:**
- Manual: nhấn "Check for update" → dialog "Có bản X.Y.Z mới. Tải về?" → tải + restart
- Auto: 1 lần mỗi 24h khi app start → nếu có bản mới hiện toast "Bản mới X.Y.Z sẵn sàng. Mở app để cập nhật."

> *Caveat:* Repo GitHub chưa có. Plan giả định user sẽ tạo public repo và config `GITHUB_REPO` trong `updater.py`. Lần build đầu (chưa có release) → updater silently skip.

### `autostart.py`

```python
def enable():
    startup = Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    shortcut = startup / "VNStockWatcher.lnk"
    # dùng pywin32 (win32com.client) tạo .lnk pointing đến exe với arg --tray
    ...
def disable(): shortcut.unlink(missing_ok=True)
def is_enabled() -> bool: return shortcut.exists()
```

Khi exe chạy với `--tray` → bỏ qua `gui.deiconify()`, chỉ build tray icon (chạy ẩn từ đầu).

### `config.json` schema

```json
{
  "interval": 10,
  "auto_minimize_on_start": true,
  "start_with_windows": false,
  "last_update_check": "2026-05-22T10:00:00",
  "symbols": [
    {"symbol": "VNM", "threshold": 10000, "side": "Both"},
    {"symbol": "FPT", "threshold": 5000,  "side": "BU"}
  ]
}
```

---

## Build → `.exe`

`requirements.txt`:
```
vnstock
winotify
pystray
Pillow
requests
packaging
pytz
pywin32
```

`build.bat`:
```bat
@echo off
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name VNStockWatcher ^
    --icon=assets\icon.ico ^
    --add-data "assets\icon.ico;assets" ^
    --collect-all vnstock ^
    --collect-all pystray ^
    src\main.py
echo Build done: dist\VNStockWatcher.exe
```

- `--windowed`: ẩn console
- `--collect-all vnstock`: tránh missing data/submodule
- `--add-data icon.ico`: tray cần đọc icon ở runtime
- Output ~80-100MB do nhiều deps

---

## Verification

### Dev (máy có Python)
1. `python -m venv .venv && .venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. `python src/main.py` → GUI mở + tray icon hiện
4. Thêm 1 mã đang giao dịch (vd VNM, threshold thấp 100) → Start
5. Verify:
   - Toast hiện góc phải khi có lệnh lớn
   - Log realtime trong tab Config
   - Tab Lịch sử có data, filter theo mã hoạt động
   - `history.csv` được sinh ra cạnh script, mở Excel đọc OK
   - Click X → window ẩn, tray icon vẫn còn, polling vẫn chạy (xem CSV vẫn append)
   - Right-click tray → Stop/Start/Show/Quit hoạt động
   - Bật "Start with Windows" → check shortcut xuất hiện trong `shell:startup`
6. Ngoài giờ giao dịch → status "Thị trường đóng cửa", không call API
7. Tắt mạng giữa chừng → log error, không crash, retry chu kỳ sau

### Build & ship
1. `build.bat` → có `dist\VNStockWatcher.exe`
2. Copy exe sang máy Windows **chưa cài Python** → double-click → tray icon + GUI hiện
3. Save config → `config.json` sinh ra cạnh exe
4. Sau khi có vài lệnh lớn → `history.csv` sinh ra cạnh exe

### Auto-update (test sau khi có GitHub repo)
1. Push tag `v1.0.0`, upload `VNStockWatcher.exe` vào Release
2. Bump `version.py` lên `1.0.1`, build lại, upload Release `v1.0.1`
3. Cài bản `1.0.0` xuống máy test, nhấn "Check for update" → dialog, đồng ý → app restart thành `1.0.1`

---

## Open Items (cần user cung cấp trước khi implement)

- **GitHub repo URL** cho auto-update (vd: `phuclq/chungkhoan-watcher`). Nếu chưa muốn auto-update bây giờ → tạm hardcode `GITHUB_REPO = None` và disable nút "Check for update".
- **Icon file** `assets/icon.ico`. Có thể tạm dùng icon Python default; user gửi sau.

---

## Out of Scope (cố tình bỏ — Simplicity First)

- Lịch ngày lễ tự động (user tự stop khi nghỉ lễ)
- Biểu đồ giá / phân tích kỹ thuật
- Multi-user / cloud sync
- Notification click action (mở chart, etc.)
- Code signing cho exe (Windows SmartScreen có thể cảnh báo "Unknown publisher" — bỏ qua)
- Auto-update có rollback (nếu update fail, user tải tay)
