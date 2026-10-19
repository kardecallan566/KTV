@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
 py -3 installer-local\build.py %*
) else (
 python installer-local\build.py %*
)
if errorlevel 1 (echo Falha ao gerar o pacote & pause & exit /b 1)
if not exist "release\usb\userwidget\KTV_0.4.3_BR_20261018.zip" (echo ZIP nao encontrado & pause & exit /b 1)
if not exist "release\usb\userwidget\KTVDiag_0.1.0_BR_20261018.zip" (echo ZIP de diagnostico nao encontrado & pause & exit /b 1)
if not exist "release\usb\userwidget\KTVBare_0.1.0_BR_20261018.zip" (echo ZIP Bare nao encontrado & pause & exit /b 1)
if not exist "release\usb\userwidget\KTVFlat_0.1.0_BR_20261018.zip" (echo ZIP Flat nao encontrado & pause & exit /b 1)
start "" explorer.exe "%CD%\release\usb"
echo Copie a pasta userwidget inteira para o pendrive FAT32.
pause
