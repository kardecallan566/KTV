@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py server.py
) else (
  python server.py
)
if errorlevel 1 (
  echo.
  echo O KTV Server foi encerrado com erro.
  pause
)
