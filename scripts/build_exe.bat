@echo off
chcp 65001 >/dev/null
setlocal
cd /d "%~dp0"
title 构建 TIAWebTwin.exe
echo ==============================================
echo   构建 Windows 单文件 exe（开发者一次性执行）
echo   产物：dist\TIAWebTwin.exe
echo   最终用户双击该 exe 即可，无需 Python/终端
echo ==============================================
echo.

where py >/dev/null 2>/dev/null
if errorlevel 1 (
  echo 未找到 Python launcher。构建机需要 Python 3.10+。
  pause
  exit /b 1
)

if not exist ".build-venv\Scripts\python.exe" (
  py -3 -m venv .build-venv
  if errorlevel 1 goto fail
)
".build-venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean tia_twin.spec
if errorlevel 1 goto fail

echo.
echo 构建完成：dist\TIAWebTwin.exe
echo 把该 exe 发给用户，双击运行即可。
pause
exit /b 0

:fail
echo.
echo 构建失败，请查看上面的错误信息。
pause
exit /b 1
