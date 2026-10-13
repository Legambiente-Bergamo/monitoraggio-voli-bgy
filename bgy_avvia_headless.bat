@echo off
REM bgy_avvia_headless.bat - Avvia la suite BGY in modalità headless
REM Versione 1.0.0 - INFRA-06
REM
REM Avvia scheduler + watchdog senza GUI (per task di sistema).
REM Attende che PostgreSQL sia pronto prima di partire.
REM Non richiede interazione utente.

setlocal
cd /d "%~dp0"

REM --- Attesa che PostgreSQL sia pronto (max 60s) ---
echo [%date% %time%] Attesa PostgreSQL... >> "bgy_data\bgy_logs\headless_boot.log"
set /a TENTATIVI=0

:CHECK_PG
sc query postgresql-x64-17 | findstr /C:"RUNNING" >nul
if %errorLevel% equ 0 goto PG_OK
set /a TENTATIVI+=1
if %TENTATIVI% geq 30 goto PG_TIMEOUT
timeout /t 2 /nobreak >nul
goto CHECK_PG

:PG_OK
echo [%date% %time%] PostgreSQL pronto, avvio suite headless >> "bgy_data\bgy_logs\headless_boot.log"

REM --- Avvia scheduler in background (no finestra) ---
start "" /B py -3.12 bgy_scheduler.py

REM --- Attesa 5s per lasciare avviare lo scheduler ---
timeout /t 5 /nobreak >nul

REM --- Avvia watchdog in background ---
start "" /B py -3.12 bgy_watchdog.py

echo [%date% %time%] Suite headless avviata >> "bgy_data\bgy_logs\headless_boot.log"
exit /b 0

:PG_TIMEOUT
echo [%date% %time%] TIMEOUT: PostgreSQL non pronto dopo 60s >> "bgy_data\bgy_logs\headless_boot.log"
exit /b 1