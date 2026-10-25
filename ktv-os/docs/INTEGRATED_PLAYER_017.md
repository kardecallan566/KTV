# KTV OS Alpha 0.17 — TV integrada, sem sites externos na tela Canais

## Objetivo

O KTV OS é o ambiente de reprodução. Na seção Canais, **não há atalhos que abrem sites completos de emissoras**. Para canais com streaming livre, o mpv reproduz a transmissão localmente, em tela cheia. Em casos em que a emissora publicou especificamente um **player incorporável**, o KTV exibe **somente o iframe oficial** dentro do diálogo de vídeo com moldura/controles do KTV OS, mantendo nome da fonte visível. Não fazemos scraping ou remoção de HTML/CSS em páginas externas.

## Primeiros dois players verificados

- TV Brasil (EBC): fonte https://aovivo.ebc.com.br/ — iframe publicado oficialmente `https://aovivo.ebc.com.br/embed-tvbrasil.html`.
- TV Cultura (Cultura Play): https://culturaplay.tvcultura.com.br/channels/14-01-tv-cultura-ao-vivo — iframe publicado oficialmente `https://culturaplay.tvcultura.com.br/channels/14/embed`.

A incorporação pode falhar por mudança de política de iframe, cookies, rede, codec, autorização, DRM ou compatibilidade do navegador. O KTV não consegue inspecionar nem controlar inteiramente o conteúdo dentro de um iframe de origem externa.

A Pluto TV fica **somente com mpv**, pois os termos públicos da Pluto restringem incorporar seu player a outros aplicativos. Não fazemos iframe do site Pluto nem tentamos ocultar seus anúncios, DRM ou identificadores.

## TV aberta

A área TV aberta agora mostra somente canais com transmissão direta na lista pública KTV: TV Brasil, Canal Gov, TV Câmara, Canal Educação e TV Cultura. Todos têm botão para reproduzir em mpv. TV Brasil e TV Cultura também possuem botão **Player da emissora** para assistir no iframe oficial sem abrir outro site.

**SBT, Globo, Record e Band foram retirados dos atalhos de TV**, porque ainda não foi identificado um player direto/incorporável cuja integração no app esteja autorizada e que funcione sem fluxo de login/DRM. O usuário pode continuar usando a antena do televisor Samsung.

## Segurança e transparência

- `GET /api/smart-player/options` valida `kind` e `id` no catálogo, fornecendo URL apenas dentre duas constantes HTTPS.
- O front-end verifica novamente o endereço em uma lista fechada antes de usar `iframe.src`; não há URL do usuário nem URL M3U na incorporação.
- O iframe usa atributos `sandbox`, `referrerpolicy` e `allow` mínimos para reprodução; o servidor aplica CSP `frame-src` restrita aos dois domínios.
- `POST /api/smart-player/open` e `POST /api/tv-aberta/open` foram removidos: nenhum canal abre sites completos do provedor.
- Ao fechar o diálogo, `iframe.src` é removido para parar streaming e descarregar conteúdo externo.
- A interface mostra a marca/fonte da emissora. Não tenta fazer o usuário acreditar que o player externo foi desenvolvido pelo KTV.

**Sem anúncios próprios do KTV** não significa ausência total de anúncios: uma transmissão gratuita pode conter intervalos comerciais, anúncios no vídeo ou controles próprios do player. Não removemos, manipulamos nem contornamos publicidade, avisos de consentimento ou mecanismos de acesso dos provedores.

## Teste

```bash
python -m unittest discover -s ktv-os/tests -v
node --check ktv-os/app/app.js
bash ktv-os/linux-live/build-iso.sh --check
```

A ISO Alpha **0.17 amd64** é para PC Intel/AMD conectado via HDMI à TV, não para Raspberry Pi ARM64. Após gerar a ISO no GitHub, testar TV Brasil em mpv e iframe EBC; TV Cultura em mpv e iframe Cultura Play; fechar o player e conferir cessação da transmissão; canais Pluto mpv; teclado virtual; Wi-Fi; desligamento e HDMI. Testes unitários não garantem que o browser consiga renderizar o iframe na sua rede.

## Referências

- https://aovivo.ebc.com.br/
- https://culturaplay.tvcultura.com.br/channels/14-01-tv-cultura-ao-vivo
- https://legal.paramount.com/us/en/plutotv/terms-of-use?r=pluto.tv
