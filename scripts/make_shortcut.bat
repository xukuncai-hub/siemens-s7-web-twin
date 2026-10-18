@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0"

echo Creating Desktop Shortcut...

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'TIA Web 3D Twin.lnk')); $s.TargetPath = '%~dp0start.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'TIA Web 3D Twin'; $s.Save()"

if errorlevel 0 (
    echo.
    echo ==============================================
    echo Success! Shortcut created on your Desktop:
    echo    [TIA Web 3D Twin]
    echo ==============================================
) else (
    echo Failed to create shortcut.
)
echo.
pause
