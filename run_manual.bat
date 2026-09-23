@echo off
REM Manual mode: no camera needed. Up/Down = glass +/-. Right = 100%, Left = clear.
REM NOTE: use the real python.exe by absolute path. A bare "python" may resolve to
REM the 0-byte Microsoft Store placeholder in WindowsApps and fail to start.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" -u glass_overlay.py --manual
pause