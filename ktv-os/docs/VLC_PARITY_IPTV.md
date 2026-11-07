# KTV OS — evolução de reprodução IPTV (mpv)

## Objetivo
Aproximar a experiência dos streams M3U/MPEG-TS da robustez observada no VLC. VLC e KTV podem usar bibliotecas, demuxers, cache e decoders diferentes; portanto, um link funcionando no VLC é um excelente caso de diagnóstico, não garantia automática de equivalência.

## Ajustes de reprodução
- mpv usa demuxer em thread separada e cache de rede com limites de memória por perfil.
- `cache-pause=yes`: quando a rede seca o buffer, o player pausa/rebufferiza em vez de continuar consumindo frames sem dados.
- `cache-pause-wait=3`: exige até 3 segundos de dados para sair do rebuffer (respeitando cache disponível).
- `cache-pause-initial=no`: não atrasa desnecessariamente a primeira imagem.
- MPEG-TS e HLS usam opções libavformat de reconexão; `reconnect_at_eof` é aplicado somente ao HLS para evitar loop em TS finito.
- Threads de decoder deixam de ser fixadas em 1; mpv/libavcodec escolhem paralelismo automático conforme compilação e CPU.
- `framedrop=vo` preserva a continuidade do decoder e descarta apenas frames atrasados na saída quando necessário.

## Raspberry Pi 3
O perfil economy mantém cache/demux dentro de um orçamento de memória conservador. Não forçamos resolução, FPS nem decoder de hardware: o stream e os codecs reais variam, e aceleração disponível depende do sistema/driver/build do mpv. O perfil não reduz qualidade de imagem por transcodificação; seleciona variante HLS quando a playlist oferece alternativas.

## Comparação reproduzível com VLC
Para cada canal que VLC reproduz bem e KTV falha, registrar:
1. URL (privada/sensível: não publicar; usar amostra sanitizada ou host de teste).
2. Tipo: MPEG-TS direto, HLS playlist, redirect, autenticação/referer.
3. Codec/resolução/FPS/bitrate; áudio e vídeo.
4. Tempo até primeiro frame, buffer, contadores de decoder/VO, avsync e estado de áudio.
5. Resultado no mesmo hardware, rede e período.

Testar uma alteração por vez e guardar o log mpv com `--log-file` em ambiente de diagnóstico. Logs podem conter URL/token; remover credenciais antes de compartilhar.

## Limitações honestas
- A telemetria mpv não observa diretamente os pixels HDMI.
- `audio-pts` e faixa selecionada não provam que o som está audível.
- Reconexão depende de servidor, protocolo e libavformat; alguns TS contínuos encerram a conexão sem EOF formal.
- Automatizar fallback sem evidência pode piorar Pi 3, por isso decoder alternativo é limitado e conservador.

## Testes
No diretório `ktv-os`: `python -m unittest tests.test_player` ou `python -m unittest discover -s tests`. Os testes de argumentos não medem throughput, qualidade visual nem compatibilidade física.
