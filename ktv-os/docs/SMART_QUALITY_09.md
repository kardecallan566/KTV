# KTV OS Alpha 0.9 — Smart Quality (primeiro checkpoint)

## Escopo implementado

- Perfis de HLS escolhidos antes da reprodução: **Econômico** (menor variante), **Equilibrado** (alvo inicial 4 Mb/s na seleção de variante), **Melhor disponível** (maior variante). O player mpv recebe `--hls-bitrate` e orçamento limitado de cache; MP4/local não usa a opção HLS.
- Painel informativo opcional que consulta `/api/player/status` somente durante a reprodução, a cada 2,5 segundos. Exibe dimensões do vídeo, codec, FPS estimado, quadros perdidos, buffer e decodificador **apenas quando disponibilizados pelo mpv**.
- Diagnóstico por socket Unix criado em diretório temporário local, com timeout curto, limite de tamanho e propriedades fixas. Não expõe TCP nem URL de comando ao navegador.
- Opções do navegador validadas estritamente no servidor: não são repassados argumentos arbitrários ao executável. Sem transcodificação ou IA.

## Limitações honestas

- A escolha de variante de `--hls-bitrate` ocorre no início, **não equivale a ABR automático ou detector de largura de banda**.
- Streams com playlist simples ou variante fixa podem ignorar a seleção. MP4 e mídias locais não sofrem alteração na resolução.
- Um stream de origem SD não ganha detalhes reais de HD. O player continua tentando `--hwdec=auto-safe` com fallback conforme instalação.
- Os números medidos dependem da versão de mpv e FFmpeg e podem aparecer como indisponíveis. A interface não promete medição de qualidade de rede, bitrate real ou aceleração de GPU.
- A imagem Debian Live atual é AMD64 (PC), **não é uma imagem ARM64 de Raspberry Pi**.
- Canais públicos atuais são experimentais e não foram revalidados em hardware Samsung nesta entrega.

## Como testar no PC

1. Baixe/construa a branch deste checkpoint no PC (não grave na TV Samsung).
2. Execute `python -m unittest discover -s ktv-os/tests -v` e `node --check ktv-os/app/app.js`.
3. Execute o KTV OS com o mpv no PATH ou inicie a imagem Linux Live gerada pelo CI da própria branch.
4. Na tela **Canais**, selecione um perfil. Reproduza um canal autorizado HLS e volte à tela KTV OS para observar as métricas.
5. Compare os modos em streams com master playlist multivariantes; em streams sem variantes, não espere diferenças.
6. Confirme saída HDMI, Wi-Fi, controle, volume e desligamento, sem alterar configurações do sistema permanentemente.

## Próximas etapas

- Verificar comportamento e FPS por codec/driver em hardware real.
- Descobrir de maneira segura as variantes publicadas pelo provedor e apresentar resolução/bitrate declarados, sem acessar IPs internos ou URLs privadas.
- Construir **imagem ARM64 separada** para Raspberry Pi 4/5 após definição de hardware e testes de DRM/KMS, áudio HDMI e drivers.
- Filtros leves A/B, watchdog de queda de frames e IA somente após benchmarks locais.
