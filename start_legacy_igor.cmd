@echo off
setlocal
set "taskIgorExe=%IGOR_LEGACY_EXE%"
if not defined taskIgorExe set "taskIgorExe=C:\Program Files\WaveMetrics\Igor Pro 9 Folder\IgorBinaries_x64\Igor64.exe"
if not exist "%taskIgorExe%" (
  echo Igor64.exe not found. Set IGOR_LEGACY_EXE to the installed executable.
  pause
  exit /b 1
)
if not exist "%~dp0local\igor-repair\launch.itx" (
  echo Local legacy procedure capture/build is required. See igor\compatibility\README.txt.
  pause
  exit /b 1
)
rem /I opens a separate instance and protects existing experiments. Never use /N.
start "" "%taskIgorExe%" /I "%~dp0local\igor-repair\launch.itx"
