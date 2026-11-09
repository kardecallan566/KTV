@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements-windows.txt
if errorlevel 1 exit /b 1
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name KTV-App --collect-all webview --collect-all clr_loader --add-data "app;app" --add-data "iptv_free_catalog.json;." ktv_app.py
if errorlevel 1 exit /b 1

rem Include MPV in local builds whenever mpv.exe is available on PATH.
where mpv.exe >nul 2>&1
if not errorlevel 1 (
  for %%I in (mpv.exe) do set "MPV_EXE=%%~$PATH:I"
  for %%I in ("%MPV_EXE%") do set "MPV_DIR=%%~dpI"
  if not exist "dist\KTV-App\mpv" mkdir "dist\KTV-App\mpv"
  xcopy "%MPV_DIR%*" "dist\KTV-App\mpv\" /E /I /Y >nul
  echo MPV incluido em dist\KTV-App\mpv
) else (
  echo AVISO: mpv.exe nao encontrado no PATH. O app sera compilado sem MPV.
  echo Para IPTV, instale MPV ou use o build oficial que inclui MPV.
)
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
echo.
pause
