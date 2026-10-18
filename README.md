# KTV — Samsung Legacy / Orsay local MVP

Protótipo experimental para Samsung **UN43J5200AG (firmware informado: 1080)**. Exibe imagens e vídeos servidos por um computador na mesma rede e aceita comandos por um painel web local.

**Status:** código e testes locais concluídos; **instalação e reprodução ainda não foram confirmadas na TV física**. Não substitui o sistema Samsung. Não utiliza Cloudflare ou GitHub Pages nesta fase.

## Comece por aqui (Windows)

1. Instale Python 3.10+ e mantenha o PC e a TV na mesma rede Wi-Fi/cabo.
2. Extraia o ZIP do projeto (não execute dentro de um ZIP).
3. No Windows, clique em `start_ktv.bat` ou abra PowerShell dentro da pasta KTV e execute:

   ```powershell
   py -3 installer-local/server.py
   ```

4. O terminal mostrará o IP, a URL do painel, o token administrativo e o ZIP USB.
5. No navegador do PC, abra `http://IP_DO_PC/admin/`, insira o **TOKEN ADMIN** do terminal e envie uma imagem JPG/PNG.
6. Para o primeiro teste sem TV, abra `http://IP_DO_PC/preview/` em outra aba e clique em **+ Adicionar** e **Salvar e enviar à TV**.
7. Para instalar, tente o método **sincronização LAN**, descrito em [`docs/INSTALACAO_TV.md`](docs/INSTALACAO_TV.md). Também geramos um ZIP de teste em `release/usb/userwidget/` para a hipótese USB.

> **Importante:** para sincronização Orsay, a TV costuma solicitar apenas o IP, e o instalador usa **porta 80**. `--port 8000` é bom para testar no computador, mas provavelmente não serve para sincronização pela TV.

### Endpoints

| Caminho | Uso |
|---|---|
| `/admin/` | Painel administrativo (token do terminal) |
| `/preview/` | Simulação do player no navegador |
| `/widgetlist.xml` | Lista de aplicativos Samsung Orsay |
| `/Widget/KTV_0.4.1_BR_20261018.zip` | Pacote de widget para sincronização |
| `/api/state` | Playlist e comandos consultados pela TV |
| `/api/health` | Status do servidor |

## Controles do player

- **Esquerda / direita:** mídia anterior / próxima.
- **Enter:** pausar ou retomar.
- **Seta para cima:** mostrar ou esconder informações.
- **Seta para baixo:** forçar consulta ao servidor.

## Requisitos e limites

- Windows, Linux ou macOS, **apenas Python 3.10+**, sem pacotes externos.
- Mídias: PNG, JPG, GIF e MP4. Recomendado vídeo **MP4 H.264/AAC**, mas o HTML5 `<video>` pode não funcionar neste firmware Orsay, que talvez exija API de vídeo proprietária.
- Upload máximo por arquivo: **100 MB** (limite ajustável no código).
- O servidor **não deve ser publicado na internet**; token via HTTP é aceitável somente como teste em LAN confiável.
- Estado e mídias ficam em `.ktv/` e não são versionados.
- A sincronização USB pode exigir assinatura `.sig` ou não estar habilitada no firmware. Não altere firmware nem use menu de atualização de software.

## Construção manual

```powershell
py -3 installer-local/build.py --ip 192.168.1.50 --port 80
```

O processo cria `release/Widget/...zip`, `release/widgetlist.xml` e `release/usb/userwidget/...zip`. O script `server.py` executa esse build automaticamente ao iniciar.

## Testes automáticos

```powershell
py -3 -m unittest discover -s tests -v
```

Também execute `node --check tv-orsay/js/app.js` se tiver Node.js. Consulte [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) e [`docs/INSTALACAO_TV.md`](docs/INSTALACAO_TV.md).

## Referências de compatibilidade

- [Samsung — suporte UN43J5200AG](https://www.samsung.com/br/support/model/UN43J5200AGXZD/)
- [Samsung — código legado Orsay](https://github.com/Samsung/cordova-sectv-orsay)
- [Jellyfin Orsay Installer — sincronização via rede](https://github.com/Apps2Samsung/Jellyfin-Orsay-Installer)
- [Emby Orsay — instalação para séries H e J5200](https://emby.media/community/topic/9869-samsung-orsay-smarttv-2011-2015-community-app-install-instructions/)


## Fase 2 - validar reproducao na Samsung

A sincronizacao LAN foi confirmada na linha J5200, firmware 1080. Atualize o projeto e sincronize novamente para instalar a versao **0.3.0**. O navegador e o aplicativo instalado sao identificados separadamente pelo servidor, sem autenticacao do aparelho (uso somente LAN).

1. Pare o servidor com Ctrl+C e execute `git pull origin main`. Reinicie `python installer-local/server.py`.
2. No painel `http://IP_DO_PC/admin/`, faca upload de uma imagem JPG pequena, adicione a playlist e clique em **Salvar e enviar a TV**.
3. Abra o **KTV Local** instalado no Smart Hub e acompanhe o painel **Televisao**: deve aparecer `App Orsay online` e depois `image-loaded`. Esse evento indica que o navegador carregou o arquivo, nao comprova que o painel de LCD exibiu os pixels; confira visualmente.
4. Se carregar a imagem, faca o teste com MP4 H.264/AAC curto. A API HTML5 da Samsung Legacy pode nao decodificar MP4 e exigira integracao com o player Orsay.
5. Se o painel disser `Preview online` mas nao `App Orsay online`, confira se abriu o aplicativo instalado em vez do WebBrowser, e se a versao 0.3 foi sincronizada no Smart Hub.

Nenhuma transmissao e feita pela nuvem nesta fase; nao encaminhe a porta 80 no roteador. A API `/api/event` e diagnostica e **nao autentica o aparelho**; qualquer dispositivo na LAN pode enviar esses eventos.


## Checkpoint: HLS local v0.4

Integração experimental da reprodução de HLS pelo plugin Samsung Legacy, com cadastro de canais diretos `.m3u8` no painel e gerador local de teste `gerar_hls_teste.bat`. **Ainda depende de verificação física na Samsung J5200 firmware 1080.** Requer `git pull`, reiniciar servidor e executar uma nova sincronização do aplicativo. Consulte [docs/HLS_TESTE.md](docs/HLS_TESTE.md). O navegador web pode não reproduzir HLS: use o aplicativo instalado. Não faça proxy de canais não autorizados.

## KTV 0.4.1 — Correção de abertura

Corrigida a divergência entre o nome do pacote e a versão interna do widget Orsay. Agora o plugin HLS só é criado ao pressionar ENTER, evitando acionar vídeo nativo na inicialização. Consulte [docs/DIAGNOSTICO_INICIALIZACAO.md](docs/DIAGNOSTICO_INICIALIZACAO.md) para atualizar a Samsung e validar o diagnóstico.
