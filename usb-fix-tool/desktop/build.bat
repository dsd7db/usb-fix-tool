@echo off
REM ===========================================================
REM  USB Fix Tool - Windows build script
REM  Produces dist\USBFixTool\USBFixTool.exe
REM ===========================================================
setlocal

where py >nul 2>&1
if errorlevel 1 (
    echo [error] Python launcher "py" not found. Install Python 3.10+ first.
    exit /b 1
)

echo [1/3] Creating virtual environment...
py -3 -m venv .venv || goto :err
call .venv\Scripts\activate || goto :err

echo [2/3] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || goto :err

echo [3/3] Building executable...
pyinstaller --noconfirm build.spec || goto :err

echo.
echo Done.  Run dist\USBFixTool\USBFixTool.exe
exit /b 0

:err
echo Build failed.
exit /b 1
