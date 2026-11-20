# KTV Server IPTV

Servidor independente para preparar canais IPTV no computador e entregar um HLS mais compatível ao aplicativo KTV instalado na Samsung Smart TV.

## Executar no Windows

Requisitos:
- Python 3.9+
- FFmpeg instalado e disponível no PATH (recomendado para o modo de processamento)
- TV e computador na mesma rede local

Abra o terminal nesta pasta e execute:

```powershell
py server.py
```

Ou execute `start_server.bat`.

O terminal mostra o endereço do servidor, o número de canais e se o processamento FFmpeg está ativo. O padrão usa a porta 80.

### Instalar FFmpeg

Instale uma compilação FFmpeg para Windows e adicione a pasta `bin` ao PATH do Windows. Feche e abra novamente o terminal; confirme com:

```powershell
ffmpeg -version
```

Se o executável estiver em outro local, inicie informando o caminho:

```powershell
py server.py --ffmpeg "C:\\ffmpeg\\bin\\ffmpeg.exe"
```

Se a porta 80 estiver ocupada:

```powershell
py server.py --port 8787
```

Para escolher outra playlist:

```powershell
py server.py --playlist "https://exemplo.com/lista.m3u"
```

## Processamento feito no computador

Quando FFmpeg está disponível, o modo automático prepara o canal solicitado sob demanda:

- recebe o HLS original no computador;
- converte o vídeo para H.264, perfil Main, pixel format YUV420P e até 720p;
- converte o áudio para AAC estéreo;
- gera uma nova saída HLS com segmentos MPEG-TS curtos;
- entrega à Samsung somente a playlist e os segmentos já preparados;
- mantém apenas o canal solicitado em transcodificação para evitar ocupar CPU com centenas de canais que ninguém está assistindo.

A conversão começa quando a TV solicita o manifesto do canal. A primeira abertura pode demorar alguns segundos enquanto o FFmpeg inicializa e gera os primeiros segmentos. O catálogo atualiza a cada cinco minutos sem reiniciar a sessão ativa.

O modo automático usa FFmpeg se ele estiver instalado. Sem FFmpeg, o servidor entra em modo direto e entrega o endereço original — nesse modo não há conversão nem redução da carga de compatibilidade na TV.

Para exigir transcodificação e falhar se FFmpeg não estiver instalado:

```powershell
py server.py --mode transcode
```

Para desativar a conversão:

```powershell
py server.py --mode direct
```

## Endereços

- `http://IP-DO-PC/api/state` — integração com o aplicativo Samsung.
- `http://IP-DO-PC/api/channels` — catálogo JSON.
- `http://IP-DO-PC/playlist.m3u` — playlist de saída.
- `http://IP-DO-PC/api/health` — diagnóstico, quantidade de canais e modo de processamento.

Configure no aplicativo KTV da TV o endereço base exibido no terminal. Libere a porta escolhida no Firewall do Windows para redes privadas.

## Limites importantes

A Samsung ainda precisa decodificar e exibir o H.264/AAC; isso é inerente à reprodução de vídeo. O servidor assume a conversão de codecs, preparação HLS e gestão do fluxo. A transcodificação exige CPU e pode exigir bastante processamento; por padrão há somente um canal convertido por vez. A capacidade depende do processador do computador e da resolução/bitrate da fonte.

Nem todo canal é garantido: links indisponíveis, DRM, formatos de entrada não suportados pelo FFmpeg ou restrições do provedor podem impedir a conversão. Este servidor não remove DRM.

Versão: **0.3.0**
