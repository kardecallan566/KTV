@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo      KTV - Preparar aplicativo para pendrive
echo ================================================
echo.
echo O IP do computador sera detectado automaticamente.
echo Se voce usa VPN, WSL ou varias redes, informe manualmente:
echo   preparar_pendrive.bat --ip 192.168.1.50

echo.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 installer-local\build.py %*
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python 3 nao encontrado no PATH.
        echo Instale Python 3.10+ e habilite a opcao Add to PATH.
        pause
        exit /b 1
    )
    python installer-local\build.py %*
)
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao preparar o aplicativo KTV.
    pause
    exit /b 1
)

if not exist "release\usb\userwidget\KTV_0.3.0_BR_20261018.zip" (
    echo [ERRO] Pacote esperado nao encontrado.
    pause
    exit /b 1
)

echo.
echo [OK] Aplicativo preparado. O Explorador sera aberto.
echo COPIE A PASTA userwidget INTEIRA para a RAIZ do pendrive FAT32.
echo NAO extraia o ZIP dentro de userwidget.
echo Mantenha o servidor KTV ligado no computador para exibir midias.
echo.
start "" explorer.exe "%CD%\release\usb"
pause
