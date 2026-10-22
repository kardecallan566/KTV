@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 launcher.py --open %*
) else (
  python launcher.py --open %*
)
if errorlevel 1 (
  echo Falha ao iniciar KTV OS. Confira Python 3.
  pause
  exit /b 1
)
