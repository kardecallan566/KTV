@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements-windows.txt
if errorlevel 1 exit /b 1
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name KTV-App --collect-all webview --collect-all clr_loader --add-data "app;app" --add-data "iptv_free_catalog.json;." ktv_app.py
if errorlevel 1 exit /b 1
echo.
echo Build concluido: dist\KTV-App\KTV-App.exe
where ISCC >nul 2>&1
if not errorlevel 1 (
  ISCC windows\KTV-App.iss
  if errorlevel 1 exit /b 1
  echo Instalador criado em installer-output\KTV-App-Setup.exe
) else (
  echo Inno Setup nao encontrado. A pasta dist pode ser executada diretamente.
  echo Para criar o Setup, instale Inno Setup e compile windows\KTV-App.iss
)
echo MPV ainda deve estar instalado no Windows para reproduzir IPTV e videos.
pause
