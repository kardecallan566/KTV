# KTV OS Alpha 0.19 — Recuperação automática Pluto TV

## Falha reproduzível da arquitetura anterior

A fonte comunitária BuddyChewChew contém URLs Pluto TV HLS com JWT assinado e validade limitada. A Alpha 0.18 consulta a playlist sob demanda e mantém o cache durante cinco minutos. Quando um player termina ou o HLS fica congelado, a interface só mostrava uma mensagem e o usuário precisava voltar e abrir o canal novamente. Isso não implica necessariamente DRM.

## Nova política de recuperação

O novo controlador `pluto_recovery.py` acompanha **apenas o canal Pluto que o usuário selecionou**; não fica baixando canais, não varre milhares de links e não atua em mídia, antena ou canais pessoais.

- `mpv` recebe `--keep-open=yes` para não fechar por fim normal de playlist HLS; cache limitado a 15 segundos, timeout de rede de 20 segundos e demuxer assíncrono.
- O supervisor verifica a cada **5 segundos** o estado do `mpv`. Se o processo morrer ou a playlist terminar, tenta recuperar o mesmo ID Pluto **com atualização obrigatória da playlist M3U**, conservando nome, perfil de qualidade e modo de decodificação.
- Quando a telemetria do vídeo estiver disponível, um travamento efetivo do tempo de reprodução por mais de **75 segundos**, após pelo menos 90 segundos de partida, também dispara recuperação. Quando o usuário pausou o canal, ou a telemetria está ausente, não provoca um reinício baseado apenas em suposições.
- O `mpv` para Pluto usa atalhos **Q, q e fechar janela com código de saída 77**. O supervisor interpreta esses fechamentos como intenção do usuário e **não** reabre o canal.
- O comando **Parar**, a troca para outro canal, mídia USB ou antena e o encerramento do servidor cancelam a sessão. Reabertura após cancelamento nunca é disparada por uma busca de URL atrasada.
- Tentativas repetidas seguem intervalos de 3, 8, 20, 45, 90 e 120 segundos; após **7 falhas**, interrompe a reconexão automática e exibe mensagem clara. Depois de uso estável por 40 segundos, a contagem volta a zero. Isso protege o Raspberry Pi e evita pressionar a CDN em caso de indisponibilidade prolongada.

### Segurança e privacidade

- O navegador transmite **somente o ID hexadecimal do canal**. O servidor não devolve JWT, cookies nem endereço assinado em nenhuma resposta de status/telemetria.
- Novos URLs vêm exclusivamente da mesma playlist HTTPS fixa, sem redirects, e passam pelo validador rígido do host/path Pluto.
- Não existe proxy local, cache de segmentos, extração de chaves, bypass de DRM, remoção de anúncios ou autenticação em serviços pagos.
- As falhas internas são descritas sem incluir os URLs assinados nos logs/status do KTV.
- Esta recuperação não interfere nos controles do sintonizador ISDB-Tb, Wi-Fi, outros canais ou desligamento.

## Limites e como testar

A recuperação **não pode garantir sinal perpétuo** se a fonte pública/community playlist também estiver com JWT expirado, se houver restrição geográfica, queda persistente de rede, exigência de autenticação ou bloqueio do serviço. O backoff interrompe loops de falha. Fontes comunitárias não equivalem a contrato de disponibilidade do provedor.

No hardware HDMI/Samsung, assista por pelo menos 30–60 minutos ao mesmo canal Pluto e observe o status "reconexão automática". Teste retirar e recolocar rede durante transmissão, fechar manualmente com **Q** e apertar **Parar** na interface — nenhum dos dois deve reabrir sozinho. Teste também troca entre Pluto, IPTV e TV aberta por antena.

### Testes automatizados

```bash
python -m unittest discover -s ktv-os/tests -v
node --check ktv-os/app/app.js
bash ktv-os/linux-live/build-iso.sh --check
```

ISO: **KTV-OS-Alpha-0.19-amd64.iso** (PC). Futura imagem Raspberry Pi ARM64 permanece pendente.

## Próxima etapa: canais pagos, sem contornar proteções

A KTV pode criar um catálogo de **provedores autorizados** e uma integração com suas APIs/SDKs licenciadas, permitindo login legítimo e reprodução dentro do app quando o provedor permitir. Outra possibilidade é sintonizador/decodificador oficial que exponha saída permitida. Assinatura ou criptografia de um canal não autoriza automaticamente copiar seus streams, tokens ou licenças.

Os requisitos de compatibilidade para Widevine/PlayReady e ARM64 precisam ser negociados/testados separadamente com os provedores. Nenhum link de canal pago de origem desconhecida será adicionado como solução temporária.
