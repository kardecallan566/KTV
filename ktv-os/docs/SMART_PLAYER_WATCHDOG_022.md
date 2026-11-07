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
