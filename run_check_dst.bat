@echo off
REM run_check_dst.bat - Lancia check_dst per la notte DST
REM Uso: run_check_dst.bat [YYYY-MM-DD]
REM Default: 2026-10-24 (notte DST)

setlocal
set PROJECT_ROOT=C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5
set NIGHT=%1
if "%NIGHT%"=="" set NIGHT=2026-10-24

cd /d "%PROJECT_ROOT%"
py -3.12 -m bgy_tools.check_dst --night %NIGHT% > "%PROJECT_ROOT%\bgy_data\bgy_logs\check_dst_auto_%NIGHT%.log" 2>&1
set RC=%ERRORLEVEL%
echo Check DST completato (exit %RC%). Log: bgy_data\bgy_logs\check_dst_auto_%NIGHT%.log
exit /b %RC%