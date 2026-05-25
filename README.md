# VNStock Watcher

Windows desktop app theo doi lenh khop khoi luong lon cua chung khoan Viet Nam bang `vnstock`.

## Chay dev

Yeu cau Python 3.11.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src\main.py
```

Khi chay dev, app luu `config.json` va `history.db` tai project root. Khi chay ban build, cac file nay nam canh file `.exe`.

Neu ton tai `history.csv` cu va `history.db` chua co, app se tu import du lieu sang SQLite roi doi ten file cu thanh `history.csv.bak`.

## Build exe

```bat
build.bat
```

`build.bat` se tao/dung `.venv`, cai dependencies, cai PyInstaller va build `dist\VNStockWatcher.exe`. Neu co `assets\icon.ico`, build se dung icon do cho exe va tray. Neu chua co icon, app van build va tray dung icon ve tam.

## Auto-update

Mac dinh auto-update dang tat vi chua co GitHub repo public. Khi co repo, sua `GITHUB_REPO` trong `src/updater.py` thanh dang `owner/repo`, sau do publish release co file `.exe`.

## Ghi chu

- Theo doi chi goi API trong gio giao dich: thu 2 den thu 6, 09:00-11:30 va 13:00-15:00.
- Lan quet dau sau khi Start chi lay moc du lieu, khong bao lai lich su cu.
- Toast co cooldown 30 giay moi ma de tranh spam, nhung history/log van duoc ghi day du.
- Nut dong cua so chi an app xuong tray. Thoat han bang menu tray.
