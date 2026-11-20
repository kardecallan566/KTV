# KTV Server IPTV

Servidor independente para disponibilizar canais IPTV HLS ao aplicativo KTV já instalado na Samsung Smart TV. Esta pasta contém somente o servidor; não é necessário alterar ou reinstalar o aplicativo da TV.

## Executar

Requisitos: Python 3.9+ e computador/TV na mesma rede local.

No Windows, abra o terminal nesta pasta e execute:

```powershell
py server.py
```

Ou dê duplo clique em `start_server.bat`.

O terminal informa o IP do computador, a quantidade de canais HLS carregados e o endereço que deve estar configurado como servidor no aplicativo KTV da TV. Por padrão usa a porta 80.

Se a porta 80 já estiver ocupada ou você não puder usá-la:

```powershell
py server.py --port 8787
```

Se quiser usar outra playlist M3U:

```powershell
py server.py --playlist "https://exemplo.com/lista.m3u"
```

Para informar manualmente o IP anunciado à TV:

```powershell
py server.py --ip 192.168.1.20
```

## O que o servidor faz

- Baixa a playlist M3U configurada e extrai os canais com URLs HLS (.m3u8).
- Carrega a playlist reserva histórica se a lista principal estiver vazia, indisponível ou reduzida.
- Mantém o catálogo em memória e atualiza a playlist a cada cinco minutos, sem interromper a sessão do canal que a TV já estiver reproduzindo.
- Entrega ao KTV Orsay o estado esperado em `/api/state`, com cada canal como item `hls` e sua URL de transmissão.
- Disponibiliza `/api/channels`, `/playlist.m3u` e `/api/health` para diagnóstico.

## Endereços

- `http://IP-DO-PC/api/state` — integração com o aplicativo Samsung.
- `http://IP-DO-PC/api/channels` — catálogo JSON.
- `http://IP-DO-PC/playlist.m3u` — playlist gerada pelo servidor.
- `http://IP-DO-PC/api/health` — estado do servidor.

A TV e o computador precisam estar na mesma rede. Permita a porta escolhida no Firewall do Windows para redes privadas. Não exponha o servidor diretamente à Internet.

## Compatibilidade

O cliente KTV Orsay usa o player HLS nativo da Samsung. Por isso, o servidor anuncia URLs HLS diretamente; não converte fluxos TS, não transcodifica vídeo e não promete que todo canal da playlist será compatível com o firmware da TV. A reprodução depende também da disponibilidade do link de origem e dos codecs/limitações do aparelho.

Versão: **0.2.0**
