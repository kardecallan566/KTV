# Playlist IPTV externa — Windows

**Fonte padrão:** `https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u`  
**Importação observada:** 1.834 canais únicos, 53 categorias e 3.662 entradas de transmissão (1.831 HLS e 1.831 TS).  
**Formato local:** `ktv-iptv-playlist-v3`.

## Funcionamento

Ao abrir a seção **Canais → Playlist externa**, o KTV Windows baixa novamente a M3U do GitHub e atualiza o catálogo local. A atualização manual usa o mesmo fluxo. Se a rede ou a fonte estiver indisponível, o aplicativo mantém e apresenta a última cópia válida salva localmente.

O parser associa cada `#EXTINF` à linha de mídia seguinte e importa:

- Nome do canal e `tvg-id`.
- Categoria `group-title`, removendo os sufixos técnicos `[M3U8]` e `[TS]`.
- Logo `tvg-logo`, quando for uma URL HTTP(S) válida.
- Variantes de transmissão HLS (`.m3u8`) e TS (`.ts`).

Entradas repetidas do mesmo canal são agrupadas pelo identificador e nome normalizado. As variantes HLS e TS são preservadas. A interface mostra um botão de reprodução para cada formato disponível.

## Reprodução e proteção das fontes

Os endereços de transmissão ficam no arquivo local `iptv_free_catalog.json`, dentro do diretório de estado do KTV. A interface web recebe apenas o ID do canal e os formatos disponíveis; não recebe as URLs de transmissão. Quando o usuário escolhe um formato, o servidor resolve o ID no catálogo local e entrega a URL diretamente ao MPV.

As URLs passam pela validação de `stream_urls.py`: somente HTTP(S), portas web permitidas, hosts públicos e formatos diretos suportados. O cabeçalho M3U/EPG não é usado como endereço de reprodução. Os endereços não são devolvidos pela API nem expostos à interface web. Como o MPV mantém diagnósticos locais, o arquivo de log pode registrar a fonte atualmente aberta; revise-o antes de compartilhá-lo.

## Configuração e limites

A URL padrão pode ser substituída por uma variável de ambiente do Windows:

```powershell
$env:KTV_EXTERNAL_PLAYLIST_URL = "https://raw.githubusercontent.com/owner/repo/branch/list.m3u"
```

A fonte precisa ser HTTPS no host `raw.githubusercontent.com`; o download é limitado a 8 MB e redirecionamentos para outro host são rejeitados. O arquivo local é substituído atomicamente somente depois que a playlist é validada e contém canais com streams utilizáveis.

A integração é exclusiva do KTV Windows. Não altera canais pessoais, catálogos público/comunitário/Pluto ou favoritos existentes. O MPV tenta HLS primeiro por padrão; quando uma entrada possui as duas variantes, o usuário também pode selecionar TS.

A disponibilidade de cada canal depende da fonte e da rede. O KTV não pode garantir que um servidor remoto permaneça online ou que todos os formatos sejam aceitos em qualquer computador. Use a playlist e as transmissões somente quando tiver autorização para acessá-las.
