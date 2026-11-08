@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Instale Python 3.10 ou superior antes de continuar.
  pause
  exit /b 1
)
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements-windows.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias do KTV App.
  pause
  exit /b 1
)
echo.
echo KTV App pronto para iniciar pelo iniciar_windows.bat
pause
