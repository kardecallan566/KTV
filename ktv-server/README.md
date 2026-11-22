# KTV Server IPTV

Servidor independente para preparar canais IPTV no computador e entregar HLS compatível ao aplicativo KTV ou ao navegador da Samsung Smart TV.

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
- converte o vídeo para H.264, perfil Baseline, sem B-frames, pixel format YUV420P e até 1280 pixels de largura;
- converte o áudio para AAC estéreo;
- gera uma nova saída HLS com segmentos MPEG-TS de 5 segundos, keyframes alinhados e janela de 12 segmentos para oferecer mais margem de buffer;
- entrega à Samsung somente a playlist e os segmentos já preparados;
- mantém apenas o canal solicitado em transcodificação para evitar ocupar CPU com centenas de canais que ninguém está assistindo.

A conversão começa quando a TV solicita o manifesto do canal. A primeira abertura pode demorar alguns segundos enquanto o FFmpeg inicializa e gera os primeiros segmentos. O HLS publica arquivos temporários somente depois de concluir cada segmento. O FFmpeg não força reconexão em EOF ou HTTP 404, pois repetir recursos expirados pode travar o fluxo. A versão 0.5.1 testou conexões HTTP não persistentes na leitura HLS, mas esse experimento foi revertido na versão 0.5.2 após piora da estabilidade observada em testes. Cada canal só é convertido quando um dispositivo solicita seu manifesto ou segmentos; se não houver novas solicitações por 90 segundos, o processo daquele canal é encerrado automaticamente. Enquanto há espectadores, um monitor verifica se novos segmentos estão sendo produzidos; se a origem parar de entregar dados por cerca de 35 segundos, o KTV encerra o processo FFmpeg antigo, aguarda sua finalização e inicia uma nova conexão, respeitando um intervalo mínimo entre tentativas. No player `/watch/ID`, um monitor adicional detecta quando o tempo do vídeo deixa de avançar por 20 segundos e tenta recarregar o fluxo automaticamente, sem exigir que o usuário volte à lista de canais. Canais não acessados nunca são convertidos. O catálogo atualiza a cada cinco minutos sem reiniciar a sessão ativa. O diagnóstico de cada processo FFmpeg é gravado em `data/hls/ID-DO-CANAL/ffmpeg.log`. A numeração dos segmentos muda a cada inicialização para evitar que a TV reutilize segmentos antigos em cache. A rota `/api/stream/ID-DO-CANAL` informa se o FFmpeg está ativo, quantos segmentos existem, a idade do segmento mais recente e o manifesto HLS atual, sem expor a URL de origem ou seus tokens.

O modo automático usa FFmpeg se ele estiver instalado. Sem FFmpeg, o servidor entra em modo direto e entrega o endereço original — nesse modo não há conversão nem redução da carga de compatibilidade na TV.

Para exigir transcodificação e falhar se FFmpeg não estiver instalado:

```powershell
py server.py --mode transcode
```

Para desativar a conversão:

```powershell
py server.py --mode direct
```

## Compatibilidade com Samsung Legacy

A rota `/api/state` mantém o contrato esperado pelo aplicativo Samsung: `version` numérico, `items`, `index` e `playing`. Para reduzir o trabalho do navegador antigo, cada item contém somente `name`, `type`, `url` e `duration`. O JSON é compacto e caracteres fora de ASCII são escapados, evitando dependência de interpretação de codificação no firmware.

## Endereços

- `http://IP-DO-PC/api/state` — integração com o aplicativo Samsung.
- `http://IP-DO-PC/api/channels` — catálogo JSON.
- `http://IP-DO-PC/playlist.m3u` — playlist de saída.
- `http://IP-DO-PC/` e `/tv-info/` — páginas de diagnóstico compatíveis com versões anteriores.
- `http://IP-DO-PC/watch` — catálogo de canais para abrir diretamente no navegador da TV.
- `http://IP-DO-PC/watch/ID-DO-CANAL` — player HTML5 para um canal específico (o ID é obtido ao abrir o catálogo).
- `http://IP-DO-PC/state` — alias legado do catálogo JSON; equivale a `/api/state`.
- `http://IP-DO-PC/api/health` — diagnóstico, quantidade de canais e modo de processamento.
- `http://IP-DO-PC/api/stream/ID-DO-CANAL` — diagnóstico técnico do HLS de um canal específico.

### Assistir diretamente pelo navegador da Samsung

Com o servidor ligado, abra no navegador da TV:

```text
http://IP-DO-PC/watch
```

Pesquise o canal e selecione-o. O servidor abre uma página HTML5 com player de vídeo e controles. Se o FFmpeg estiver ativo, o player recebe o HLS convertido pelo próprio computador em H.264/AAC e segmentos MPEG-TS. O primeiro acesso pode levar alguns segundos para preparar o fluxo.

Se o navegador não iniciar sozinho, pressione PLAY no controle remoto. Alguns navegadores antigos bloqueiam reprodução automática com áudio. A página usa JavaScript ES5 simples e seleciona HLS ou MP4 conforme o que o navegador declara suportar. A indicação `probably` de MP4 é apenas uma estimativa do navegador, não uma garantia de reprodução.

Para esse teste, mantenha o modo automático ou use `--mode transcode`. No modo `direct`, o navegador recebe a URL HLS original, que pode não ser compatível com a TV. Se o player mostrar erro ou tentar baixar o manifesto, isso indica uma limitação do navegador/firmware ou da fonte, e não confirma falha do catálogo do aplicativo.

Configure também no aplicativo KTV da TV o endereço base exibido no terminal. Libere a porta escolhida no Firewall do Windows para redes privadas.

## Limites importantes

A Samsung ainda precisa decodificar e exibir o H.264/AAC; isso é inerente à reprodução de vídeo. O servidor assume a conversão de codecs, preparação HLS e gestão do fluxo. A transcodificação exige CPU e pode exigir bastante processamento; por padrão há somente um canal convertido por vez. A capacidade depende do processador do computador e da resolução/bitrate da fonte.

Nem todo canal é garantido: links indisponíveis, DRM, formatos de entrada não suportados pelo FFmpeg ou restrições do provedor podem impedir a conversão. Este servidor não remove DRM.

Versão: **1.0.0**


Na versão 0.3.3, a página inicial de diagnóstico foi simplificada para navegadores Samsung antigos e não oferece links diretos para endpoints JSON/M3U. Esses endpoints continuam disponíveis para o aplicativo KTV e para players compatíveis. A versão 0.4.0 acrescenta o catálogo `/watch` e o player HTML5 `/watch/ID`, sem remover as rotas existentes. A versão 0.5.0 reforça a recuperação de processos FFmpeg travados e adiciona recuperação automática no player do navegador. A versão 0.5.1 testou conexões HTTP não persistentes; a versão 0.5.2 reverte essa experiência e retorna ao comportamento padrão do FFmpeg. A versão 0.6.0 ajusta o H.264 para perfil Baseline, alinha os keyframes aos segmentos HLS, usa numeração exclusiva de segmentos após reinícios e adiciona diagnóstico individual do fluxo. A versão 0.7.0 mantém o HLS para dispositivos compatíveis e adiciona um fluxo MP4 fragmentado experimental. A versão 0.8.0 acrescenta MJPEG de baixa resolução para navegadores sem HLS nativo. A versão 0.9.0 melhora a imagem para até 854 pixels e 12 quadros por segundo, e adiciona áudio MP3 em uma conexão separada. A versão 0.9.1 mantém a conexão MJPEG aberta e reinicia a sessão FFmpeg quando a origem IPTV encerra o fluxo. A versão 1.0.0 aplica reconexão independente ao áudio MP3 e ajusta o MJPEG para 10 fps e qualidade JPEG 7, buscando reduzir picos de tráfego e travamentos em Wi-Fi 2,4 GHz. Áudio e vídeo continuam em conexões separadas, portanto a sincronização não é garantida. A sincronização entre áudio e vídeo pode variar porque são duas sessões FFmpeg independentes; a compatibilidade de MP3 contínuo precisa ser validada no navegador Samsung.
