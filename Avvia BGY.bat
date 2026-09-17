@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo  BGY Monitoring Suite - Avvio
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 1. Trova pythonw.exe
REM ------------------------------------------------------------
set "PYTHONW="

REM 1a. Prova con py launcher (raccomandato)
where py >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('py -3.12 -c "import sys, os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))" 2^>nul') do (
        if exist "%%i" set "PYTHONW=%%i"
    )
)

REM 1b. Se non trovato, prova con python nel PATH
if not defined PYTHONW (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%i in ('python -c "import sys, os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))" 2^>nul') do (
            if exist "%%i" set "PYTHONW=%%i"
        )
    )
)

REM 1c. Fallback: cerca in AppData utente corrente
if not defined PYTHONW (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
        set "PYTHONW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    )
)

if not defined PYTHONW (
    echo [ERRORE] Python 3.12 non trovato.
    echo Installa Python da https://www.python.org/downloads/
    echo e assicurati che sia nel PATH.
    pause
    exit /b 1
)

echo [OK] Python trovato: !PYTHONW!
echo.

REM ------------------------------------------------------------
REM 2. Termina istanze precedenti (GUI + scheduler + watchdog)
REM ------------------------------------------------------------
echo Chiusura istanze precedenti...
powershell -NoProfile -Command ^
    "Get-WmiObject Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*bgy_gui*' -or $_.CommandLine -like '*bgy_scheduler*' -or $_.CommandLine -like '*bgy_watchdog*' } | ForEach-Object { Write-Host ('  Termino PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo Pulizia completata.
echo.
timeout /t 3 /nobreak >nul

REM ------------------------------------------------------------
REM 3. Avvio GUI
REM ------------------------------------------------------------
echo Avvio GUI...
start "" "!PYTHONW!" "%~dp0bgy_gui.py"

exit /b 0