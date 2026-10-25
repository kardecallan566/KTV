# KTV OS Alpha 0.12 — Navegador, playlists M3U e recuperação de reprodução

## Entregue

- **Navegador de internet:** item no menu e atalho na tela inicial. A busca é encaminhada pelo servidor **local** para uma nova janela do Chromium já instalado na imagem Debian Live. Abre DuckDuckGo com a consulta codificada (não executa comandos de busca). Depois de abrir, o usuário pode navegar normalmente pelo Chromium. `Alt+Tab` volta ao quiosque, `Alt+F4` fecha a janela adicional. O navegador não é incorporado em iframe porque muitos sites bloqueiam incorporação.
- **M3U no padrão Kodi:** na aba Canais, cole uma playlist M3U própria/autorizada, com `#EXTM3U` e pares `#EXTINF` e URL direta. Importa nomes e categorias; suporta streams HTTP(S) terminados em `.m3u8` ou `.mp4`. Ignora duplicatas, caminhos locais, protocolos especiais (como `plugin://`) e parâmetros de complementos Kodi. **Não** instala nem executa código de complementos, não baixa playlists remotas nem faz scraping de sites.
- Limites de segurança: texto de playlist até **96 KiB**, corpo JSON até **128 KiB** nessa rota; listas pessoais até **250 canais**, com renderização paginada de 36 cartões; backup USB preservado e gravação atômica. O limite de 256 KiB do arquivo de backup ainda se aplica.
- **Modo compatível no player:** se houver áudio sem imagem, imagem preta ou travamento, pressione `Q` para sair do mpv e selecione **Tentar modo compatível** no diálogo KTV OS. Usa `--hwdec=no --vo=x11 --profile=sw-fast`; pode consumir mais CPU, especialmente em ARM, e não está habilitado automaticamente. O padrão ainda usa `--hwdec=auto-safe`. O diálogo também reporta código de saída do mpv quando disponível.
- O player consulta se o mpv declarou saída de vídeo renderizada. Essa informação é apenas diagnóstico; não garante que a TV mostre pixels, não mede DRM e não identifica de forma conclusiva a causa da falha.

## Fontes e direitos de uso

A URL `https://reidoscanais.cam/canais` mostra transmissões de serviços comerciais pagos e afirma indexar fontes de terceiros. **Não foi integrada à ISO** por falta de comprovação de autorização para retransmissões. Nenhum método de extração de tokens, cookies, DRM ou proteção contra cópia foi implementado.

O projeto Kodi oferece o complemento oficial **IPTV Simple Client**, que **recebe** playlists M3U/XMLTV fornecidas por terceiros; o Kodi não concede por si só licenças nem entrega os canais. Adotamos o **formato M3U** (sem instalar complementos não oficiais) para fontes que o usuário possui permissão de assistir.

Referências oficiais:
- https://kodi.wiki/view/Add-on:IPTV_Simple_Client
- https://kodi.wiki/view/Free_content
- https://mpv.io/manual/stable/

## Testes e limites

No repositório:
```bash
python -m unittest discover -s ktv-os/tests -v
node --check ktv-os/app/app.js
bash ktv-os/linux-live/build-iso.sh --check
```

No hardware PC conectado por HDMI à Samsung: validar Wi-Fi, TV pública, Pluto TV, M3U própria, som/HDMI e desligamento. Testar o mesmo canal em modo normal e compatível. Se o mpv/Chromium encerrar sozinho, coletar `ktv-os-diagnostics` e, se possível, informar o nome do canal e codec/resolução.

A ISO **Alpha 0.12 amd64** continua voltada a PCs Intel/AMD. Raspberry Pi ARM64, upscaling por IA, vídeo autenticado/DRM, EPG XMLTV e ABR automático permanecem pendentes.
