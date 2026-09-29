@echo off
REM Avvia BGY.bat - Avvia la BGY Monitoring Suite
REM Versione 2.0.0 - Auto-elevazione UAC (F11e-2)
REM
REM Se il processo non è elevato, richiede privilegi amministrativi
REM e si riavvia. Questo è necessario per il riavvio automatico del
REM servizio PostgreSQL (watchdog).

setlocal

REM --- Verifica se il processo è elevato ---
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ========================================================
    echo   Richiesta privilegi amministrativi...
    echo ========================================================
    echo.
    echo La suite ha bisogno di privilegi admin per:
    echo   - Riavviare automaticamente il servizio PostgreSQL
    echo     in caso di crash
    echo.
    echo Windows mostrera' una richiesta UAC. Clicca "Si".
    echo.
    powershell -NoProfile -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

REM --- Da qui in poi il processo e' elevato ---
cd /d "%~dp0"

echo.
echo ========================================================
echo   BGY Monitoring Suite
echo   Avvio con privilegi amministrativi
echo ========================================================
echo.

REM Verifica dipendenze (come nel file originale)
py -3.12 -c "import sys; sys.exit(0)" >nul 2>&1
if %errorLevel% neq 0 (
    echo ERRORE: Python 3.12 non trovato.
    echo Verifica l'installazione e riprova.
    pause
    exit /b 1
)

REM Avvia la GUI
py -3.12 bgy_gui.py

endlocal