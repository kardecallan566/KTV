@echo off
setlocal EnableExtensions
title KTV OS - Preparador de Pendrive

echo ==========================================
echo       KTV OS - PREPARADOR USB (Windows)
echo ==========================================
echo.
echo Este programa copia/atualiza o KTV OS no pendrive.
echo Nao formata o dispositivo.
echo A pasta .ktv-config (favoritos e configuracoes) sera preservada.
echo.

set "SOURCE=%~dp0.."
for %%I in ("%SOURCE%") do set "SOURCE=%%~fI"
if not exist "%SOURCE%\launcher.py" (
  echo ERRO: nao encontrei launcher.py em:
  echo "%SOURCE%"
  echo.
  echo Execute este BAT dentro da pasta do projeto KTV baixado/clonado.
  pause
  exit /b 1
)

echo Unidades disponiveis:
powershell -NoProfile -Command "Get-CimInstance Win32_LogicalDisk | Where-Object {$_.DriveType -in 2,3} | ForEach-Object { '{0}  {1}  ({2})' -f $_.DeviceID,$_.VolumeName,$_.Size }"
echo.
set /p "DRIVE=Digite a letra do pendrive (ex.: E): "
set "DRIVE=%DRIVE: =%"
if "%DRIVE:~-1%"==":" set "DRIVE=%DRIVE:~0,-1%"
set "USB=%DRIVE%:"
if not exist "%USB%\NUL" (
  echo ERRO: unidade "%USB%" nao encontrada.
  pause
  exit /b 1
)

echo.
echo Origem: "%SOURCE%"
echo Destino: "%USB%\ktv-os"
echo.
choice /c SN /n /m "Continuar? [S/N] "
if errorlevel 2 exit /b 0

echo.
echo Copiando arquivos do KTV OS...
robocopy "%SOURCE%" "%USB%\ktv-os" /MIR /R:2 /W:2 /XD ".git" "__pycache__" /XF "*.pyc"
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
  echo.
  echo ERRO: falha na copia. Codigo Robocopy: %RC%
  pause
  exit /b %RC%
)

if not exist "%USB%\.ktv-config" mkdir "%USB%\.ktv-config"
echo.
echo ==========================================
echo Preparacao concluida!
echo Pendrive: %USB%
echo KTV OS:   %USB%\ktv-os
echo Config.:  %USB%\.ktv-config
echo ==========================================
echo.
echo Ejete o pendrive com seguranca e conecte-o ao Raspberry Pi.
pause
exit /b 0
