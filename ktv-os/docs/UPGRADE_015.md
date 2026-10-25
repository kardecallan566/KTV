# KTV OS Alpha 0.15 — teclado arrastável, correção Pluto, saúde do stream e programação

## Diagnóstico da falha Pluto TV

A playlist brasileira BuddyChewChew/pluto tem 179 entradas com endereços de aproximadamente **2.869 caracteres**, com parâmetros de sessão/JWT. A Alpha 0.14 passou a validar toda URL HTTP(S) remota com limite de 1.800 caracteres antes de chamar o mpv, o que bloqueou **todos** os canais da Pluto — regressão confirmada no código.

A Alpha 0.15 mantém o limite de 1.800 para endereços genéricos, mas admite até 6.000 caracteres **somente** para HTTPS no host exato `ipv4.pluto.tv`, com caminho estrito de um canal hexadecimal de 24 caracteres e `master.m3u8` com JWT presente. Essa exceção não se aplica a URLs arbitrárias. Ela permite novamente entregar o stream ao mpv; não garante que JWT esteja válido ou que a Pluto aceite acesso no seu dispositivo/região. Nenhuma sessão, token ou cookie é incluído em logs ou respostas da API.

## Teclado virtual

- Botão flutuante alterna explicitamente entre Abrir e Fechar.
- Três abas: ABC, símbolos/números e acentos (pt-BR), além de espaço, Enter, Shift e Backspace.
- Arraste pela barra superior verde, com mouse ou toque; posição fica limitada ao espaço visível.
- Ao fechar/reabrir, o teclado **volta à posição original** — nenhuma posição é armazenada.
- O teclado X11 para sites externos permanece manual e independente.

## Verificação de reprodução

O KTV OS faz uma sondagem HTTP HEAD de no máximo 4 segundos **antes da tentativa de reproduzir canais públicos, Pluto e do catálogo GitHub**, consultando apenas os URLs resolvidos no servidor a partir de IDs conhecidos. Resultado é guardado por 90 s. O browser nunca envia URL arbitrária para a sonda, e canais pessoais não são sondados remotamente para evitar SSRF.

Estados: `reachable` (servidor respondeu), `unavailable` (404/410), `restricted` (401/403, pode funcionar ao reproduzir), `unverified` (indeterminado/timeout). Apenas indisponibilidade explícita impede abertura; dúvidas ainda permitem tentar o mpv. **Sondagem de URL não garante áudio, vídeo, decodificador, DRM ou estabilidade:** o usuário precisa validar a reprodução real.

## EPG real: Agora e A seguir

A interface mostra a programação em cada cartão quando há título e horário no XMLTV, ou informa ausência de dados. Fontes fixas, acionadas quando a tela Canais é aberta:
- Brasil: `https://iptv-epg.org/files/epg-br.xml.gz`
- Pluto TV Brasil: `https://i.mjh.nz/PlutoTV/br.xml.gz`

Download restrito por tamanho/timeout, sem redirects ou DTD/entidades XML. Cache de 5 minutos, sem requisições no boot. Não calcula grade fictícia. Correspondência por identificador do canal no XMLTV ou nome normalizado; alguns canais não possuem correspondência e ficam sem guia. Os dados EPG de fontes comunitárias são experimentais.

## TV aberta e mais fontes

Uma seção **TV aberta — sites oficiais** oferece atalhos para SBT, Globo/Globoplay, Record/RecordPlus, Band, TV Cultura, TV Brasil e Rede Vida. Cada um abre somente a URL oficial em uma janela do Chromium, sem copiar fluxos protegidos, dispensar login ou contornar DRM. O sintonizador DVB-T/ISDB-T da Samsung continua sendo opção para recepção por antena.

A seção de canais GitHub passa a ler também `iptv-org/iptv/master/streams/br.m3u`, com filtragem de hosts HTTPS aprovada por lista rígida. Não integra cópias de Globo/SBT de CDNs desconhecidas nem garante direitos de redistribuição.

## Testes e limitações

- `python -m unittest discover -s ktv-os/tests -v`
- `node --check ktv-os/app/app.js && node --check ktv-os/app/osk.js`
- `bash ktv-os/linux-live/build-iso.sh --check`

ISO **Alpha 0.15 amd64**, ainda não imagem ARM64 Raspberry Pi. Confirmar em PC/HDMI Samsung os canais Pluto que falhavam, reprodução do vídeo com som, Wi-Fi, desligamento, teclado móvel, EPG e atalhos oficiais. Para mensagens 401/403, testar site oficial/condições do serviço; não tentar contornar autenticação ou DRM.
