@echo off
setlocal
cd /d "%~dp0"
title TIA Web Twin

echo ==============================================
echo   TIA Web Twin
echo   Starting local services...
echo   Close this window to stop.
echo ==============================================
echo.

set "PY="
for /f "delims=" %%I in ('where python 2^>nul') do (
  echo %%I | findstr /i /v "WindowsApps" >nul
  if not errorlevel 1 (
    if not defined PY set "PY=%%I"
  )
)

if not defined PY (
  where py >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)

if not defined PY (
  echo [ERROR] Python not found. Please install Python 3.10+.
  pause
  exit /b 1
)

"%PY%" -c "import snap7" >nul 2>nul
if errorlevel 1 goto install
"%PY%" -c "import websockets" >nul 2>nul
if errorlevel 1 goto install
goto run

:install
echo Installing dependencies (snap7, websockets)...
"%PY%" -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
if errorlevel 1 (
  echo [ERROR] Failed to install dependencies.
  pause
  exit /b 1
)

:run
echo Starting Digital Twin server and opening browser...
"%PY%" run_twin.py
echo.
echo ==============================================
echo   TIA Web Twin stopped.
echo ==============================================
pause
exit /b 0
