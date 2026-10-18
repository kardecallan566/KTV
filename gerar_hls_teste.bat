@echo off
setlocal
cd /d "%~dp0"
where ffmpeg >nul 2>&1
if errorlevel 1 (
 echo [ERRO] ffmpeg nao encontrado no PATH. Instale ou ajuste o PATH.
 pause
 exit /b 1
)
if not exist ".ktv\hls" mkdir ".ktv\hls"
echo.
echo === KTV HLS - SINAL DE TESTE LOCAL ===
echo Mantenha o servidor KTV aberto em OUTRO terminal.
echo Este sinal e gerado no computador e NAO usa canais de terceiros.
echo Cadastre no KTV Admin: http://SEU-IP/hls/demo.m3u8
(echo.)
ffmpeg -hide_banner -loglevel warning -re -f lavfi -i "testsrc2=size=854x480:rate=25" -f lavfi -i "sine=frequency=440:sample_rate=44100" -c:v libx264 -preset veryfast -tune zerolatency -pix_fmt yuv420p -profile:v baseline -level 3.1 -b:v 900k -g 50 -keyint_min 50 -sc_threshold 0 -c:a aac -b:a 96k -f hls -hls_time 4 -hls_list_size 6 -hls_flags delete_segments+omit_endlist -hls_segment_filename ".ktv/hls/demo_%%05d.ts" ".ktv/hls/demo.m3u8"
if errorlevel 1 echo [ERRO] FFmpeg encerrou com erro. Veja o log acima.
pause
