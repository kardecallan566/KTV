# Smart Player — Watchdog e reconexão (checkpoint)

## Comportamento

- Monitora o avanço de `time-pos` do mpv e distingue pausa manual.
- Aguarda 35 s de estabilização e considera travamento após 60 s sem progresso.
- Para streams HTTP(S) previamente validados e cadastrados, solicita até 3 reconexões automáticas.
- Cada reconexão reaproveita a sessão autorizada (URL, perfil e headers definidos no catálogo), sem aceitar comandos ou URLs novos vindos da interface.
- Pluto TV permanece no controlador próprio, que renova sua sessão; não é replay de URL expirada.
- Troca manual de canal e Stop invalidam a sessão de recuperação anterior.
- Telemetria mostra estado, tempo sem progresso, tentativas e reconexão em andamento.

## Limitações e validação

O watchdog observa o relógio da mídia. Uma transmissão cujo timestamp não avance pode ser classificada como travada; por isso o limite é conservador. Não detecta congelamento visual com timestamp avançando, nem silêncio de áudio. A recuperação tenta reabrir o stream; não garante que o servidor remoto esteja disponível.

Testes automatizados cobrem estado saudável, pausa, travamento, sessão recuperável e bloqueio de sessão não registrada. CI e reprodução real em hardware são validações separadas.


## Diagnóstico de áudio e sincronização A/V

- A telemetria agora diferencia faixa de áudio ausente, conteúdo somente áudio e faixa de vídeo detectada sem renderização confirmada.
- Streams somente áudio não acionam o fallback de decodificação de vídeo por software; isso evita reinícios desnecessários em rádios e transmissões de áudio.
- Exibe bitrate, velocidade e PTS de áudio quando o mpv fornece esses valores.
- A sincronização A/V é mostrada em segundos; valores absolutos a partir de 250 ms recebem aviso e a partir de 500 ms recebem alerta mais forte.
- Esses indicadores são diagnósticos, não correção automática de atraso. A disponibilidade das propriedades depende do stream, do decoder e do mpv.


## Audio Engine 2.3 — sincronização e diagnóstico do decoder

- O player nativo aceita ajuste de `audio-delay` em tempo real pelo IPC Unix privado; a API local recebe somente um número limitado a ±5 segundos.
- A interface oferece passos de 100 ms, reset e indicação do atraso aplicado. O ajuste vale para a sessão atual; ao fechar/reabrir o canal, o mpv retorna ao padrão.
- O endpoint exige player mpv ativo e não expõe comandos arbitrários do IPC.
- A telemetria diferencia frames descartados na saída e no decoder. A partir de 120 frames descartados pelo decoder, mostra aviso de pressão; isso é um sinal de diagnóstico, não prova congelamento nem escolhe decoder automaticamente.
- O contador de frames descartados é cumulativo na sessão mpv. Avalie sua tendência e duração antes de concluir que há problema.
- A detecção confiável de imagem congelada ainda precisa correlacionar mudança real de frames renderizados (não apenas relógio da mídia); não deve reiniciar stream só por um contador estático.
