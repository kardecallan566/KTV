# Arquitetura do MVP local

```text
Windows / Python 3 (HTTP na LAN :80)
  ├─ /widgetlist.xml ─→ Smart Hub App Sync (Orsay)
  ├─ /Widget/*.zip ──→ pacote KTV para instalação
  ├─ /admin/ ────────→ controle pelo navegador no PC ou celular
  ├─ /api/admin/* ──→ uploads e comandos autenticados com token
  ├─ /api/state ────→ consulta a cada 4s pelo KTV Player
  ├─ /media/* ──────→ imagens e vídeos com suporte a HTTP Range
  └─ /preview/ ─────→ simulador no navegador moderno

Samsung UN43J5200AG (Orsay)
  └─ KTV Player ES5 → /api/state → /media/*
```

## Estratégias

- KTV TV é JavaScript ES5, sem Node nem frameworks modernos, e seu config.xml é **Orsay**, não Tizen.
- Build injeta `http://IP_DO_PC` em `js/runtime-config.js` dentro do ZIP. Para IP novo, rode build novamente e resincronize.
- Servidor Python standard library: cria a playlist, aceita mídia validada, preserva estado em `.ktv/state.json` e autentica alterações com token em `.ktv/admin_token`.
- Token não entra no widget: a TV apenas consulta playlist/mídias. Qualquer aparelho na LAN consegue ler as mídias; não use dados privados neste MVP.
- O vídeo usa HTML5 `<video>` **somente como experimento**, porque decodificação em Orsay pode exigir plugin específico. Respostas de mídia aceitam `Range` para compatibilidade.
- Não existe heartbeat autenticado nesta fase; o indicador da última consulta apenas mostra requisições a `/api/state`, inclusive preview no navegador.

## Segurança e limitações

- Teste somente em rede privada confiável; **não exponha a porta 80 na internet**. Administrador manda token por HTTP sem TLS.
- Upload com extensão e assinatura permitidas, limite de 100 MB e nomes gerados no servidor. Não há antivírus ou transcodificação.
- Sem execução remota de código, sem ssh, sem root, sem alteração do firmware.
- O servidor local não tem proteção robusta contra tráfego hostil/DoS; futura API Cloudflare precisará autenticação por dispositivo, expiração de tokens, HTTPS e regras de origem.

## Fases futuras

1. Confirmar instalação real da J5200 e imagem; corrigir bugs reais reportados.
2. Investigar player multimídia Samsung Orsay e formatos.
3. Migrar admin para GitHub Pages estático, API para Cloudflare Workers/D1, mídia para R2 quando fizer sentido. **GitHub Pages sozinho não executa backend.**
4. Múltiplas TVs, autenticação/pairing e controle offline.
