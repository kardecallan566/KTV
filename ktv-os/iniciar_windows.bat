@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3.10+ nao encontrado. Execute install_windows.bat primeiro.
  pause
  exit /b 1
)
py -3 ktv_app.py
if errorlevel 1 (
  echo KTV App encerrou com erro. Consulte a mensagem exibida.
  pause
  exit /b 1
)
