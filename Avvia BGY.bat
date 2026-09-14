@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  BGY Monitoring Suite - Avvio (TEST)
echo ============================================================
echo.

echo 🔍 Chiusura istanze precedenti (GUI + scheduler + watchdog)...
powershell -NoProfile -Command ^
    "Get-WmiObject Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*bgy_gui*' -or $_.CommandLine -like '*bgy_scheduler*' -or $_.CommandLine -like '*bgy_watchdog*' } | ForEach-Object { Write-Host ('  Termino PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo ✅ Pulizia completata.
echo.
timeout /t 5 /nobreak >nul

echo 🔄 Avvio GUI...
start "" "C:\Users\NicoSorint\AppData\Local\Programs\Python\Python312\pythonw.exe" "%~dp0bgy_gui.py"

exit /b 0