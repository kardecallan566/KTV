# KTV OS Alpha 0.14 — Teclado sob controle + formatos de transmissão

## Teclado virtual

O teclado KTV abre **somente ao clicar no botão verde flutuante “⌨ Abrir teclado”**. Com o teclado aberto, o mesmo botão vira **“✕ Fechar teclado”** (amarelo) e também existe um botão Fechar no painel. O estado de expansão é anunciado via `aria-expanded` e `aria-pressed`.

O foco em caixas de texto **não ativa mais o teclado automaticamente**, inclusive quando não foi detectado teclado físico. O botão permanece sempre visível para uso com mouse. O teclado do sistema `matchbox-keyboard` para páginas externas continua sendo acionado pelo botão específico do navegador KTV Verde; também é manual e não aparece automaticamente.

## Formatos suportados para canais autorizados

| Extensão | Uso |
| --- | --- |
| `.m3u8` | HLS: playlists de variantes e canais ao vivo |
| `.mpd` | MPEG-DASH: manifests de vídeos/TV |
| `.ts` | MPEG Transport Stream: fluxo direto, pode ser apenas um segmento |
| `.mp4`, `.m4v` | Vídeo direto, transmissão ou arquivo em HTTP(S) |
| `.webm` | WebM direto |
| `.flv` | FLV legado sobre HTTP(S) |

Os formatos funcionam no cadastramento individual e na importação M3U (formato de lista). O player continua usando `mpv` nativo, sem shell e sem downloader executável de terceiros. O seletor de bitrate HLS **só** é aplicado a `.m3u8`; não prometemos selecionar variantes MPEG-DASH. Os novos formatos não implicam que todos codecs sejam aceitos, que um arquivo TS isolado seja canal contínuo ou que DRM/autenticação possam ser contornados.

No catálogo GitHub filtrado, além do HLS pré-existente, foram admitidos **manifests DASH exclusivamente no host `vs-cmaf-pushb-ww-live.akamaized.net`**, de transmissões de notícias BBC listadas na fonte, ainda sem confirmação de reprodução no hardware do usuário. Outros domínios não ganham autorização por terminarem em `.mpd`.

## Revisão de segurança

A validação centralizada `stream_urls.py` é aplicada ao armazenamento do canal **e** no player para links remotos:

- Aceita apenas HTTP(S) e portas 80, 443, 8080, 8443.
- Rejeita usuário/senha embutidos, fragmentos, caracteres de controle, URLs grandes, extensões/protocolos não suportados e linhas com flags do mpv.
- Bloqueia IPs privados, loopback, link-local, reservados e alguns hostnames internos, como `localhost`, `.local`, `.internal`, `.home.arpa` e nomes numéricos ambíguos.
- URLs diretas enviadas ao `mpv` continuam após `--` e sem avaliação por shell; fontes de catálogo são identificadas por IDs no servidor.
- Não há scraping de conteúdo privado, extração de DRM, redirecionamento deliberado de redes internas, proxy de streams, nem acesso remoto à API KTV.

**Limitação conhecida:** validar uma URL não resolve DNS, não impede mudanças posteriores de DNS nem impede redirecionamentos HTTP feitos pelo próprio player. Como playlists M3U são conteúdo não confiável, cadastre somente transmissões autorizadas e confiáveis; não cole arquivos desconhecidos com dados secretos. O servidor do KTV continua local (`127.0.0.1`). Para proteção de redes com alto risco, também seria necessário bloquear saídas privadas no nível do firewall/sandbox, fora desta versão.

## Testes e entrega

Execute `python -m unittest discover -s ktv-os/tests -v`, `node --check ktv-os/app/app.js`, `node --check ktv-os/app/osk.js` e `bash ktv-os/linux-live/build-iso.sh --check`.

A ISO gerada será **KTV-OS-Alpha-0.14-amd64.iso**. A versão Raspberry Pi requer imagem ARM64 separada. Confirme na televisão que o teclado abre e fecha por clique, que o navegador continua funcional e que HLS/HDMI/desligamento não regrediram.
