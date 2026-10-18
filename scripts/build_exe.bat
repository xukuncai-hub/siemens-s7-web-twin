@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 构建 TIAWebTwin.exe
echo ==============================================
echo   构建 Windows 单文件 exe（开发者一次性执行）
echo   产物：dist\TIAWebTwin.exe
echo   最终用户双击该 exe 即可，无需 Python/终端
echo ==============================================
echo.

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo 未找到 Python。构建机需要 Python 3.10+。
  pause
  exit /b 1
)

if not exist ".build-venv\Scripts\python.exe" (
  %PY% -m venv .build-venv
  if errorlevel 1 goto fail
)
".build-venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean tia_twin.spec
if errorlevel 1 goto fail

echo.
echo ==============================================
echo 构建完成：dist\TIAWebTwin.exe
echo 把该 exe 发给最终用户，双击运行即可，无需 Python 环境！
echo ==============================================
pause
exit /b 0

:fail
echo.
echo 构建失败，请查看上面的错误信息。
pause
exit /b 1
