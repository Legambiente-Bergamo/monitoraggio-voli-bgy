@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM ============================================================
REM  BGY Monitoring Suite - Avvio
REM  Versione 2.0 - Con verifica dipendenze e log di avvio
REM ============================================================

echo ============================================================
echo  BGY Monitoring Suite - Avvio
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 0. Cartelle e log
REM ------------------------------------------------------------
set "LOG_DIR=%~dp0bgy_data\bgy_logs"
set "STARTUP_LOG=%LOG_DIR%\startup.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

echo [%date% %time%] === AVVIO BGY === >> "%STARTUP_LOG%"

REM ------------------------------------------------------------
REM 1. Trova python.exe e pythonw.exe
REM ------------------------------------------------------------
set "PYTHON="
set "PYTHONW="

REM 1a. Prova con py launcher (raccomandato)
where py >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('py -3.12 -c "import sys, os; print(sys.executable)" 2^>nul') do (
        if exist "%%i" set "PYTHON=%%i"
    )
    for /f "delims=" %%i in ('py -3.12 -c "import sys, os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))" 2^>nul') do (
        if exist "%%i" set "PYTHONW=%%i"
    )
)

REM 1b. Se non trovato, prova con python nel PATH
if not defined PYTHON (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)" 2^>nul') do (
            if exist "%%i" set "PYTHON=%%i"
        )
        for /f "delims=" %%i in ('python -c "import sys, os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))" 2^>nul') do (
            if exist "%%i" set "PYTHONW=%%i"
        )
    )
)

REM 1c. Fallback: cerca in AppData utente corrente
if not defined PYTHON (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)
if not defined PYTHONW (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
        set "PYTHONW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    )
)

if not defined PYTHON (
    echo [ERRORE] Python 3.12 non trovato.
    echo Installa Python da https://www.python.org/downloads/
    echo e assicurati che sia nel PATH.
    echo [%date% %time%] ERRORE: Python non trovato >> "%STARTUP_LOG%"
    pause
    exit /b 1
)

if not defined PYTHONW (
    echo [ERRORE] pythonw.exe non trovato accanto a python.exe.
    echo [%date% %time%] ERRORE: pythonw.exe non trovato >> "%STARTUP_LOG%"
    pause
    exit /b 1
)

echo [OK] Python: !PYTHON!
echo [OK] pythonw: !PYTHONW!
echo.

REM ------------------------------------------------------------
REM 2. Verifica dipendenze Python
REM ------------------------------------------------------------
echo Verifica dipendenze...

"!PYTHON!" -c "import pandas, requests, bs4, schedule, playwright, matplotlib, seaborn, lxml, openpyxl, docx, reportlab, psycopg, PIL" >nul 2>&1
if !errorlevel! neq 0 (
    echo [AVVISO] Alcune dipendenze mancano. Installazione...
    echo [%date% %time%] Installazione dipendenze... >> "%STARTUP_LOG%"
    "!PYTHON!" -m pip install -r "%~dp0requirements.txt"
    if !errorlevel! neq 0 (
        echo [ERRORE] Installazione dipendenze fallita.
        echo [%date% %time%] ERRORE installazione dipendenze >> "%STARTUP_LOG%"
        pause
        exit /b 1
    )
)
echo [OK] Dipendenze Python.
echo.

REM ------------------------------------------------------------
REM 3. Verifica Playwright Chromium
REM ------------------------------------------------------------
echo Verifica Playwright Chromium...

"!PYTHON!" -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop()" >nul 2>&1
if !errorlevel! neq 0 (
    echo [AVVISO] Playwright Chromium mancante o non funzionante. Installazione...
    echo [%date% %time%] Installazione Chromium... >> "%STARTUP_LOG%"
    "!PYTHON!" -m playwright install chromium
)
echo [OK] Playwright Chromium.
echo.

REM ------------------------------------------------------------
REM 4. Verifica file di configurazione critici
REM ------------------------------------------------------------
echo Verifica configurazione...

set "CFG_MISSING=0"
if not exist "%~dp0bgy_config\config_data.json" set "CFG_MISSING=1"
if not exist "%~dp0bgy_config\config_database.json" set "CFG_MISSING=1"
if not exist "%~dp0bgy_config\config_mail.json" set "CFG_MISSING=1"

if !CFG_MISSING! equ 1 (
    echo [AVVISO] Mancano file di configurazione in bgy_config\.
    echo La GUI userà i default. Potresti doverli configurare.
    echo [%date% %time%] AVVISO: file config mancanti >> "%STARTUP_LOG%"
)
echo [OK] Configurazione.
echo.

REM ------------------------------------------------------------
REM 5. Termina istanze precedenti (GUI + scheduler + watchdog)
REM ------------------------------------------------------------
echo Chiusura istanze precedenti...

powershell -NoProfile -Command ^
    "Get-WmiObject Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*bgy_gui*' -or $_.CommandLine -like '*bgy_scheduler*' -or $_.CommandLine -like '*bgy_watchdog*' } | ForEach-Object { Write-Host ('  Termino PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo Pulizia completata.
echo.
timeout /t 2 /nobreak >nul

REM ------------------------------------------------------------
REM 6. Avvio GUI
REM ------------------------------------------------------------
echo Avvio GUI...
echo [%date% %time%] Avvio GUI >> "%STARTUP_LOG%"

start "" "!PYTHONW!" "%~dp0bgy_gui.py"

REM Attesa breve per rilevare crash immediato
timeout /t 3 /nobreak >nul

REM Verifica se GUI è ancora attiva
powershell -NoProfile -Command ^
    "if (Get-WmiObject Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*bgy_gui*' }) { exit 0 } else { exit 1 }"

if !errorlevel! neq 0 (
    echo.
    echo [ERRORE] La GUI non è partita. Controlla il log:
    echo   %LOG_DIR%\bgy_app_%date:~-4%-%date:~3,2%-%date:~0,2%.log
    echo.
    echo Ultime righe del log di startup:
    powershell -NoProfile -Command "if (Test-Path '%STARTUP_LOG%') { Get-Content '%STARTUP_LOG%' -Tail 10 }"
    echo.
    pause
    exit /b 1
)

echo [OK] GUI avviata correttamente.
echo.
echo ============================================================
echo  BGY Monitoring Suite è in esecuzione.
echo  Questa finestra si chiuderà tra 3 secondi.
echo ============================================================
timeout /t 3 /nobreak >nul
exit /b 0