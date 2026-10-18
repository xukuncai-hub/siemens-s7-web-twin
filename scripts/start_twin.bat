@echo off
chcp 65001 >/dev/null
setlocal
cd /d "%~dp0"
title TIA Web Twin
echo ==============================================
echo   TIA Web Twin
echo   关闭此窗口即停止网页与本地网关
echo ==============================================
echo.

set "PY="
where py >/dev/null 2>/dev/null
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >/dev/null 2>/dev/null
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo 未找到 Python。请先安装 Python 3.10+（安装时勾选 Add Python to PATH）。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 首次启动：正在创建 Python 环境...
  %PY% -m venv .venv
  if errorlevel 1 goto fail
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fail
  echo ok> ".venv\.deps-ok"
) else (
  if not exist ".venv\.deps-ok" (
    echo 正在安装依赖...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto fail
    echo ok> ".venv\.deps-ok"
  )
)

".venv\Scripts\python.exe" run_twin.py
if errorlevel 1 (
  echo.
  echo 启动失败，请查看上面的错误信息。
  pause
)
exit /b 0

:fail
echo.
echo 环境创建或依赖安装失败。请检查网络和 Python 安装。
pause
exit /b 1
