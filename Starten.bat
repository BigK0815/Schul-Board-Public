@echo off
setlocal
title Schul-Monitor
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" verwaltung.py
) else (
  echo Das Programm ist noch nicht eingerichtet.
  echo Bitte zuerst Einmalig_installieren.bat ausfuehren.
  pause
  exit /b 1
)
if errorlevel 1 pause
