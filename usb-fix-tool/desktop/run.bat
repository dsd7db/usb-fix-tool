@echo off
REM ===========================================================
REM  USB Fix Tool v2.3.1 - one-click launcher (run from source)
REM  Creates .venv, installs PySide6, starts the app.
REM  Right-click -> "Run as administrator" for repair/partition tools.
REM ===========================================================
setlocal
cd /d "%~dp0"

set PY=
where py >nul 2>&1 && set PY=py -3
if not defined PY (
    where python >nul 2>&1 && set PY=python
)
if not defined PY (
    echo [error] Python 3.10+ was not found.
    echo         Install it from https://www.python.org/downloads/windows/
    echo         and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    %PY% -m venv .venv || goto :err
) else (
    echo [1/3] Virtual environment found.
)

echo [2/3] Installing dependencies (first run only, ~1-2 min)...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip || goto :err
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :err

echo [3/3] Launching USB Fix Tool...
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:err
echo.
echo Setup failed. Make sure you are online and Python 3.10+ is installed.
pause
exit /b 1
