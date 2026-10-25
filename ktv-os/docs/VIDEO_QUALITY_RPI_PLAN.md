# Planejamento — qualidade de vídeo eficiente no KTV OS (Raspberry Pi)

**Estado:** somente planejamento, sem inferência de IA ativada no player.
**Meta:** melhorar a imagem perceptível sem travar a interface ou desperdiçar memória, preservando a reprodução fluida.
**Prioridade:** primeiro obter a melhor fonte disponível, depois decodificar bem, só então aprimorar os pixels.

## Base de hardware e compatibilidade

A ISO KTV OS Alpha 0.8 é **Debian Live amd64** e NÃO inicializa no Raspberry Pi ARM. Planejar imagens separadas:
- `ktv-os-amd64.iso` — desktops e mini-PCs Intel/AMD.
- `ktv-os-rpi-arm64.img.xz` — variante Raspberry Pi OS / Debian ARM64 específica para **modelo** Raspberry Pi 4/5, boot a partir de microSD/USB e pilha gráfica DRM/KMS conforme hardware.
- Nunca adicionar pacotes Raspberry Pi ou kernel ARM à ISO x86 atual sem matriz de testes.

Raspberry Pi 5: HEVC/H.265 dispõe de decodificador dedicado 4K60; H.264 e outros codecs dependem da pilha de software/CPU, com custos reais documentados no BCM2712. Raspberry Pi 4 dispõe de capacidades diferentes; deve receber perfil separado. Suporte ao decoder efetivo do `mpv` depende do kernel/FFmpeg/DRM/Mesa — **não presumir** que `--hwdec=auto-safe` acelera todos os streams.

## Pipeline proposto (eficiência primeiro)

`Link autorizado HLS` → `Master playlist / variantes` → `escolher bitrate conforme largura de banda` → `cache curto` → `decoder adequado ao codec e plataforma` → `escalonamento GPU/HVS` → `correção leve opcional` → `HDMI 1080p`.

1. **Diagnóstico da fonte**: inspecionar master playlist HTTP(S) somente ao solicitar reprodução, com timeout curto, limites de bytes e sem expor tokens. Exibir **resolução de origem, bitrate, FPS e codec se conhecidos**. Detectar quando URL aponta para variante fixa SD: não prometer 1080p onde só há 480p.
2. **Escolha de qualidade**: inicialmente permitir `Automático / Economizar / Melhor disponível`, com seleção apenas de variantes declaradas. `mpv --hls-bitrate=max` já é o padrão para master playlist na documentação atual. Implementar seleção dinâmica de verdade só após testar como `mpv` lida com rede variável e quais streams são master vs media playlist.
3. **Reprodução nativa otimizada**: manter `--no-config --no-ytdl`, whitelist de streams institucionais, hardware decode quando efetivamente suportado e fallback de software. Ajustar cache e buffer somente por perfil testado. Preferir GPU/DRM para scaling; nunca reencodar streams em tempo real quando não necessário.
4. **Filtros tradicionais leves**: considerar ajustes opcionais de `scale`, `cscale`, `deband` e nitidez discreta (evitar halos). Não inventam detalhes perdidos, mas podem tornar SD mais legível. Comparar contra imagem sem filtro.
5. **Melhoria com IA apenas opcional**: testar super-resolução espacial *pequena* em shader GPU para conteúdo até 480p/720p, eventualmente perfis NNEDI3/FSRCNNX ou alternativa compatível. Em 1080p contínuo, CNN em CPU é inadequada para Pi 4/5 sem medição satisfatória; NPU não deve ser requisito básico. Nunca executar IA se frames começarem a cair.
6. **Módulo de decisão**: regras determinísticas baseadas em origem, codec, taxa de quadros, FPS perdidos, RAM, temperatura/thermal throttling e buffer. Não usar LLM/Qwen para processar quadros. O assistente LLM (plano anterior) pode **explicar** os ajustes e sugerir perfil, não melhorar os pixels diretamente.

## Perfis iniciais a validar

| Perfil | Alvo | Ação |
| --- | --- | --- |
| Econômico | Pi 4 / rede limitada | Priorizar reprodução fluida, 720p quando necessário, sem IA, escalonamento leve |
| Equilibrado | Pi 5 / TV Full HD | Melhor variante estável até 1080p, buffer moderado, GPU scaling e decodificação eficiente |
| Qualidade | Pi 5 com sobra mensurada | Opcional deblock/deband/sharpen leve, desativação automática se cair FPS |
| Experimental IA | Hardware comprovadamente capaz | Super-resolução em teste com benchmark e rollback; jamais pré-ativada |

Valores de corte são alvos para medir, **não garantias**: alvo 30 fps com processamento total abaixo de 33,3 ms/frame ou 60 fps abaixo de 16,7 ms/frame; sem travamentos perceptíveis, 0 quadros descartados durante 5 minutos em rede estável, uso de memória previsível, baixo aquecimento. Testar também pior caso de stream 480p com muito artefato de compressão.

## Segurança e direitos

- Não acessar playlists IPTV não autorizadas, serviços pagos, DRM, redirecionadores desconhecidos ou URLs privadas de rede em uma pesquisa remota.
- HLS pode conter URLs secundárias para segmentos/chaves, inclusive em domínios distintos. Validar protocolos, limitar redirecionamentos e bytes, nunca logar tokens nem senhas. Manter testes contra SSRF, redirects para loopback, host da LAN e entradas de metadados maliciosos.
- Conteúdo remoto não é instrução para agentes de IA nem recebe permissão para executar shell.
- A IA não altera systemd, rede, canais, fontes ou desligamento sem confirmação.
- Qualidade baixa causada por stream de origem SD **não pode virar qualidade HD verdadeira**, mesmo com super-resolução.

## Entregas propostas

**Checkpoint 1 — sem IA**: dados de stream e resolução atual + seletor de qualidade + diagnóstico de buffers/quadros; categorizar fontes HD/SD e orientar usuário.

**Checkpoint 2 — ARM64**: branch e construção separada para Pi 4/Pi 5, integração gráfica e player DRM/KMS. Validar Wi-Fi, HDMI, áudio e desligamento.

**Checkpoint 3 — ajustes perceptuais**: filtros shader leves comparados por A/B, auto-desligamento por queda de FPS, opção de restaurar padrão.

**Checkpoint 4 — IA experimental**: somente após benchmark favorável, medir consumo energético/memória/CPU/GPU versus ganho subjetivo real. Manter modo sem IA como padrão.

## O que falta definir para benchmark final

- Modelo exato (Pi 4/5), quantidade de RAM (2/4/8/16 GB), arquitetura do SO e tipo de armazenamento;
- TV HDMI alvo e resolução padrão — Samsung UN43J5200AG suporta o alvo Full HD usado nos primeiros testes;
- Pelo menos três exemplos de canais com qualidade percebida baixa, identificando se têm variante HD.

## Referências

- https://mpv.io/manual/stable/
- https://www.raspberrypi.com/documentation/hardware/raspberrypi/bcm2711/
- https://www.raspberrypi.com/documentation/computers/sbcs.html
- https://www.raspberrypi.com/documentation/computers/ai.html
- https://github.com/ggml-org/llama.cpp

**Decisão:** não embarcar nem executar modelo de super-resolução ou LLM neste checkpoint. Fazer primeiro melhoria determinística e preparar arquitetura ARM64.
