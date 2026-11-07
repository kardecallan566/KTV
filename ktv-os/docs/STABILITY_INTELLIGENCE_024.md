# KTV OS 0.24 — Estabilidade inteligente

## Telemetria visual
O monitor coleta `video-params`, `video-out-params`, `time-pos`, `frame-drop-count` (frames perdidos na saída) e `decoder-frame-drop-count` (perdas no decoder). A saída inicializada + avanço da timeline é tratada como **proxy de progresso visual**, não como prova de pixels HDMI exibidos. HDMI/TV exige validação física ou captura externa.

## Tendência de frames
`FrameTrend` calcula deltas de contadores cumulativos e uma janela móvel de seis amostras. Níveis warming/stable/warning/critical evitam reagir a um pico isolado. Reset de contador não vira delta negativo.

## Smart Decoder
O fallback `compatible` é deliberado e conservador: pressão persistente no decoder, buffer acima de 8s e evidência visual/frames; no máximo uma troca automática por sessão. O modo compatível usa software decode + X11 e pode ser mais lento no Pi 3; não há troca automática agressiva de volta.

## Áudio
O diagnóstico distingue faixa ausente, telemetria indisponível e suspeita de audio-pts parado enquanto a timeline avança. `track_active` indica relógio/faixa, **não confirma áudio audível** (volume, saída HDMI, mute e amplificador ainda podem falhar).

## Raspberry Pi 3
A detecção usa `/proc/device-tree/model`. Quando o modelo identifica explicitamente Pi 3, a qualidade inicial padrão é `economy`; decoder continua `default/auto-safe`, sem forçar hwdec. Equipamento não identificado mantém `balanced`. A API `/api/player/status` expõe `profile` e `watchdog.stability`.

## Recuperação
A timeline parada continua sendo o gatilho primário (60s após grace de 35s), respeitando pausa, cooldown e limite de tentativas. A telemetria de buffer, frames, áudio e saída visual enriquece diagnóstico e decide fallback; dados ausentes não são tratados como falha comprovada.

## Verificação
Execute `python -m unittest discover -s tests` no diretório `ktv-os`. Testes automatizados não substituem teste real no Raspberry Pi 3, no stream e na TV/HDMI.
