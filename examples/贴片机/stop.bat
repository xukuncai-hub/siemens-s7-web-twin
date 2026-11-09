@echo off
setlocal
cd /d "%~dp0"
echo Stopping TIA Web Twin services...

powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { try { $_.CommandLine -like '*run_twin.py*' -or $_.CommandLine -like '*tia_gateway.py*' } catch { $false } } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo [OK] TIA Web Twin stopped.
timeout /t 2 >nul
