# KTV OS Alpha 0.13 — canais GitHub, KTV Verde e mouse

## Catálogo adicional

O sistema consulta duas fontes de playlists gratuitas, sob demanda: https://github.com/freecasthub/public-iptv e https://github.com/Free-TV/IPTV. Os links são filtrados por host HTTPS previamente revisado, formato HLS, ausência de credenciais e portas inesperadas. O catálogo nunca executa scripts dos repositórios e nunca usa a playlist para decidir argumentos do mpv. A procedência comunitária NÃO garante autorização de cada transmissão; streams comerciais, privados ou DRM não estão incluídos. As fontes mudam e canais podem estar indisponíveis ou bloqueados por região.

A lista dinâmica usa cache de 30 minutos e nunca carrega no boot. A API envia somente IDs, nomes, categorias e fonte; URLs são resolvidas no servidor somente ao dar play. Os canais públicos e Pluto TV anteriores permanecem separados. A interface pagina 36 cartões por vez.

## Navegador KTV Verde

O navegador personalizado usa uma homepage Chromium verde (browser.html, browser-green.css, browser-green.js), campos de busca grandes, atalhos e links conhecidos. Pesquisas abrem uma aba HTTPS do DuckDuckGo. É uma experiência personalizada no PORTAL: sites externos conservam seus estilos e abas padrão do Chromium. Sem iframe, proxy, remoção de anúncios ou execução de scripts externos pelo KTV.

## Teclado virtual e mouse

Todas as telas locais têm o botão Teclado, com letras, números, Enter, Espaço, Backspace, Shift e acentos comuns. A detecção Linux de teclado físico é indicativa; se não houver teclado identificado, campos de texto exibem teclado em tela. O botão fica disponível manualmente, mesmo com teclado USB ou Bluetooth conectado. Para páginas externas, o pacote leve matchbox-keyboard pode ser aberto/fechado da tela Navegador ou homepage verde. Mouse USB funciona pelo Xorg/libinput; Bluetooth depende de suporte e pareamento do sistema.

## Validação e limites

Executar os testes KTV OS, sintaxe JavaScript do app.js, osk.js e browser-green.js, e o build-iso.sh --check. Esta ISO ainda é AMD64, não imagem ARM64 do Raspberry Pi. O EPG XMLTV com fonte confiável e validação de horários continua para o próximo checkpoint. Verifique boot, Wi-Fi, HDMI, áudio, mouse, teclado, canais e desligamento em hardware real.
