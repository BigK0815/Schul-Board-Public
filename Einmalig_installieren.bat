@echo off
setlocal
cd /d "%~dp0"
title Schul-Monitor - Einmalige Installation
echo ==========================================================
echo  Schul-Monitor
echo  Einrichtung / Aktualisierung
echo ==========================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installieren.ps1"
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" (
  echo Einrichtung nicht abgeschlossen. Fehlercode: %CODE%
) else (
  echo Einrichtung erfolgreich. Starten.bat kann jetzt gestartet werden.
)
pause
exit /b %CODE%
