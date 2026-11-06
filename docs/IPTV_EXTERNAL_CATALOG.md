# Catálogo IPTV externo (snapshot)

**Origem:** [Kaiollio-cpu/iptv_free/main.m3u](https://github.com/Kaiollio-cpu/iptv_free/blob/main/main.m3u)  
**Snapshot incorporado:** 2026-11-06  
**Quantidade:** 155 entradas, 7 grupos

## O que foi integrado

O KTV OS mantém o catálogo em \`ktv-os/iptv_free_catalog.json\`, carregado por \`iptv_free_catalog.py\`. Ele aparece na tela **Canais** em uma seção independente chamada **Playlist externa**, com busca, filtro de categoria e paginação.

| Grupo | Entradas |
|---|---:|
| Esportes | 70 |
| Filmes e Séries | 30 |
| Canais Abertos | 16 |
| Variedades | 17 |
| Notícias | 5 |
| Infantil | 10 |
| Religiosos | 7 |
| **Total** | **155** |

A reprodução é solicitada por um identificador de catálogo, nunca por URL enviada pelo navegador. O servidor resolve o ID em uma lista validada; os hosts de stream aceitos estão em allowlist. O mpv recebe os dois cabeçalhos fixos que constavam na playlist (User-Agent e Referer) apenas para esta fonte.

## Separação e preservação

- Não altera \`~/.config/ktv-os/channels.json\` nem os canais pessoais já cadastrados.
- Não substitui os catálogos públicos institucionais, comunitários ou Pluto TV.
- Não importa os 155 canais automaticamente para a lista pessoal.
- Não faz download da playlist no boot; o snapshot é local e versionado.
- Se o catálogo externo falhar, os demais canais e recursos do KTV OS continuam disponíveis.

## Direitos, procedência e disponibilidade

O arquivo contém nomes de serviços de assinatura e canais comerciais. O nome \`iptv_free\` da origem não comprova que todas as transmissões sejam gratuitas ou autorizadas. A origem, direitos de retransmissão, região, estabilidade e funcionamento dos streams não foram verificados pelo projeto.

**Use somente conteúdo que você tem autorização para assistir.** A inclusão do snapshot não representa endosso, certificação de licença ou garantia de que os links continuarão ativos.

## Atualização futura

1. Baixar uma nova versão da playlist a partir da origem informada.
2. Revisar mudanças de categorias, IDs, hosts e cabeçalhos.
3. Validar todas as URLs com \`stream_urls.py\` e atualizar a allowlist apenas após revisão.
4. Regenerar o JSON preservando IDs estáveis e sem duplicatas.
5. Executar os testes de catálogo, player, API, interface e a regressão completa do GitHub Actions.
6. Integrar somente depois de confirmar que os canais pessoais e catálogos existentes permanecem intactos.
