@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements-windows.txt
if errorlevel 1 exit /b 1
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name KTV-App --collect-all webview --add-data "app;app" --add-data "iptv_free_catalog.json;." ktv_app.py
if errorlevel 1 exit /b 1
echo.
echo Build concluido: dist\KTV-App\KTV-App.exe
echo MPV deve estar instalado no Windows para reproduzir IPTV e videos.
pause
