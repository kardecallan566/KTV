# Catálogo externo M3U — somente metadados

**Fonte de metadados padrão:** repositório M3U configurado em `SOURCE_URL` no módulo `ktv-os/iptv_free_catalog.py`.  
**Snapshot atual:** 975 canais únicos em 53 categorias.  
**Formato:** `ktv-iptv-metadata-v2`.

## O que é importado

O parser lê somente os campos de cada linha `#EXTINF`:

- Nome do canal (texto após a vírgula).
- `tvg-id`, quando disponível, para identificação/EPG.
- `group-title`, normalizado como categoria.
- Categorias adicionais quando um mesmo canal aparece em mais de um grupo.

Os sufixos técnicos `[M3U8]` e `[TS]` são removidos do nome e da categoria. Registros repetidos com o mesmo `tvg-id` são agrupados para evitar duplicatas.

## O que é descartado

As linhas seguintes de cada entrada, que contêm endereços de reprodução, não são guardadas. Também são descartados:

- URLs de stream HLS e MPEG-TS.
- URLs de logos.
- User-Agent, Referer e outros cabeçalhos.
- Credenciais e parâmetros presentes nos endereços.

O JSON versionado contém somente identificadores, nomes, categorias e o campo `playable: false`. A API não devolve URLs de reprodução e a rota de player rejeita esses canais até que uma fonte de teste sintética ou autorizada seja configurada.

## Atualização no Windows

A interface **Canais → Playlist externa → Atualizar metadados** chama a rota local `POST /api/iptv-free/refresh`. A rota só executa no Windows. O módulo usa a variável:

```python
SOURCE_URL = os.environ.get(
    "KTV_EXTERNAL_PLAYLIST_METADATA_URL",
    "https://raw.githubusercontent.com/owner/repo/branch/list.m3u",
)
```

Por segurança, a fonte precisa ser HTTPS em `raw.githubusercontent.com`, a resposta é limitada a 8 MB e o redirecionamento para outro host é rejeitado. A atualização grava o novo catálogo atomicamente; se a busca ou validação falhar, o snapshot anterior permanece intacto.

## Isolamento

- Não altera canais pessoais nem `channels.json`.
- Não altera os catálogos público, comunitário ou Pluto TV.
- Favoritos continuam em arquivo separado e são preservados.
- Não habilita reprodução nem tenta resolver links M3U.
- O parser tem testes que verificam que URLs e credenciais de exemplo não aparecem no catálogo final.
