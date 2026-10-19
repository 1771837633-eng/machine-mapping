@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.9 or newer is required.
  pause
  exit /b 1
)
python tools/prepare_notebook_bridge.py
echo.
echo Existing processed CUT pilot only. Keep your current 64-bit Igor open.
start "" "http://127.0.0.1:8766/"
python -m app.server --port 8766
pause
