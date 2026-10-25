# Pluto TV Brasil — catálogo M3U comunitário (KTV OS)

Fonte configurada: `https://raw.githubusercontent.com/BuddyChewChew/pluto/refs/heads/main/pluto_br.m3u`

A playlist fornecida pelo usuário continha **179 canais em 22 categorias** na inspeção de 25/10/2026. Essa quantidade **pode mudar a qualquer momento**. Não é uma API oficial da Pluto TV nem garantia de que os streams permanecerão disponíveis.

## Como funciona

1. Abra **Canais** no KTV OS. O sistema baixa a playlist somente quando a tela de canais é aberta; não solicita a fonte no boot.
2. Um parser pequeno (`pluto_catalog.py`) aceita exclusivamente transmissões `https://ipv4.pluto.tv/api/tn/video/playout/v2/stitch/hls/channel/<ID>/master.m3u8?...jwt=...` com ID hexadecimal de 24 caracteres. Entradas com URLs de outras origens ou malformadas são ignoradas.
3. A API `GET /api/pluto/channels` retorna nomes, categorias, identificadores e procedência, mas **não inclui endereços assinados/JWTs**.
4. Ao pressionar **Assistir**, `POST /api/player/play` recebe apenas `{"kind":"pluto","id":"..."}`. O servidor consulta a lista em cache por até 5 minutos e passa a URL correspondente ao mpv.
5. Se o cache expirar, a lista é baixada novamente. Se o download falhar, o player não reutiliza um token expirado.
6. O navegador renderiza até 36 cartões por vez, com busca e filtro por categoria. **Atualizar lista** permite recarregar os metadados na tela.

## Limitações e direitos

- Os links carregam token e metadados temporários de sessão: **nunca comitar uma cópia completa da playlist** ou colocar URLs assinadas em arquivos de configuração, logs e respostas HTTP.
- Ao reproduzir, o serviço Pluto TV recebe as informações normalmente incluídas na solicitação da transmissão. A playlist comunitária pode conter parâmetros gerados em outra região/dispositivo e não funcionar em sua máquina.
- A Pluto TV disponibiliza conteúdo gratuito com publicidade, sujeito a região, direitos de catálogo, DRM e termos da plataforma. A integração não contorna essas restrições, não remove anúncios e não retransmite ou baixa vídeos.
- Links de terceiros podem expirar, desaparecer ou tornar-se incompatíveis com o mpv, principalmente se o serviço mudar autenticação/DRM. Se falharem, utilizar o aplicativo/site oficial da Pluto TV.
- A fonte externa não pode escolher parâmetros do mpv nem controlar o sistema. Somente os canais do host e formato previstos são mostrados.
- O KTV OS mantém os canais públicos e privados existentes sem alterá-los. O catálogo Pluto é exibido separadamente, sem gravar URL expirada em `channels.json`.

## Validação

Executar na branch de desenvolvimento:

```sh
python -m unittest discover -s ktv-os/tests -v
node --check ktv-os/app/app.js
```

No KTV OS (PC HDMI, com mpv instalado), abrir Canais, filtrar Anime/Filmes/Esportes, reproduzir alguns canais e testar o perfil de qualidade. Validar reprodução e áudio fisicamente; sucesso em testes automatizados **não comprova stream disponível**.

A ISO `amd64` do KTV OS ainda não inicia diretamente em Raspberry Pi ARM. A imagem ARM64 é um checkpoint separado.


## Alpha 0.10 — favoritos Pluto TV e diagnóstico

- Cada canal da seção Pluto TV passa a exibir `☆ Favoritar` / `★ Favorito`. O filtro **★ Meus favoritos** mostra apenas os escolhidos; quando o filtro está em Todas as categorias, os favoritos aparecem primeiro.
- Somente IDs hexadecimais de 24 caracteres são guardados em `~/.config/ktv-os/pluto_favorites.json`. O sistema **não persiste URLs de reprodução, JWT ou metadados de sessão**.
- A API local permite `GET /api/pluto/favorites` (lista de IDs) e `POST /api/pluto/favorites/toggle` com JSON `{"id":"<ID>"}`. Existe validação de formato, proteção de origem e gravação atômica.
- A persistência opt-in para um **segundo pendrive de dados** agora inclui IDs dos favoritos Pluto junto dos canais pessoais no snapshot. Não altera a unidade de boot, não formata pendrives e não grava no firmware da TV. Backups antigos sem o campo de favoritos continuam compatíveis. Sem persistência USB, uma sessão Linux Live reiniciada pode perder esses favoritos.
- Quando o mpv termina sozinho (por exemplo por stream temporário indisponível), a interface informa que a reprodução encerrou e sugere atualizar a lista; **não garante** distinguir fim normal, expiração, DRM ou erro de rede.
- O app e o artefato Linux Live passam a indicar **Alpha 0.10**. O arquivo esperado é `KTV-OS-Alpha-0.10-amd64.iso` (PC Intel/AMD; não Raspberry Pi ARM).

Estas alterações não removem anúncios nem contornam DRM ou bloqueios regionais.
