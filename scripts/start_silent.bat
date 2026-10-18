@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0runtime\python.exe" (
  set "PY=%~dp0runtime\python.exe"
  goto launch
)

set "PY="
for /f "delims=" %%I in ('where python 2^>nul') do (
  echo %%I | findstr /i /v "WindowsApps" >nul
  if not errorlevel 1 (
    if not defined PY set "PY=%%I"
  )
)
if not defined PY set "PY=python"

:launch

powershell -NoProfile -Command "Start-Process -FilePath '%PY%' -ArgumentList 'run_twin.py --no-browser' -WorkingDirectory '%~dp0' -WindowStyle Hidden"

echo [OK] TIA Web Twin background service started!
echo URL: http://127.0.0.1:8000/?ws=ws%%3A%%2F%%2F127.0.0.1%%3A8765%%2Fws
timeout /t 3 >nul
