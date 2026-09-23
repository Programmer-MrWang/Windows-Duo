@echo off
REM Duo glass overlay - camera driven. Live status is printed in this window.
REM Calibrate: click this window, fully open the lid, press SPACE. Esc to stop.
REM NOTE: use the real python.exe by absolute path. A bare "python" may resolve to
REM the 0-byte Microsoft Store placeholder in WindowsApps and fail to start.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" -u glass_overlay.py
pause