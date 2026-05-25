@echo off
setlocal

:: Prefer "python", fall back to "py" launcher
where python > nul 2> nul
if not errorlevel 1 (
    set PY=python
) else (
    where py > nul 2> nul
    if errorlevel 1 (
        echo Python 3.9+ required. Please install Python first.
        exit /b 1
    )
    set PY=py
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
    echo Python 3.9+ required.
    exit /b 1
)

if not exist .venv\Scripts\python.exe (
    %PY% -m venv .venv
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

python -m pip install pyinstaller
if errorlevel 1 exit /b 1

set PYINSTALLER_ARGS=--onefile --windowed --name VNStockWatcher
if exist assets\icon.ico set PYINSTALLER_ARGS=%PYINSTALLER_ARGS% --icon=assets\icon.ico --add-data "assets\icon.ico;assets"

pyinstaller %PYINSTALLER_ARGS% ^
    --collect-all vnstock ^
    --collect-all pystray ^
    src\main.py

if errorlevel 1 exit /b 1

echo Build done: dist\VNStockWatcher.exe
endlocal
