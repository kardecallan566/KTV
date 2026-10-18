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
7. **Pendrive (teste experimental):** na pasta do projeto, dê dois cliques em `preparar_pendrive.bat`. Ele gera o pacote e abre a pasta `release\usb`. Copie **a pasta `userwidget` inteira** para a raiz de um pendrive FAT32. Não extraia o ZIP contido nela. A instalação por USB pode ser bloqueada pelo firmware da Samsung.
8. Se o USB não funcionar, tente a **sincronização LAN**, descrita em [`docs/INSTALACAO_TV.md`](docs/INSTALACAO_TV.md).

> **Importante:** para sincronização Orsay, a TV costuma solicitar apenas o IP, e o instalador usa **porta 80**. `--port 8000` é bom para testar no computador, mas provavelmente não serve para sincronização pela TV.

### Endpoints

| Caminho | Uso |
|---|---|
| `/admin/` | Painel administrativo (token do terminal) |
| `/preview/` | Simulação do player no navegador |
| `/widgetlist.xml` | Lista de aplicativos Samsung Orsay |
| `/Widget/KTV_0.2.0_BR_20261017.zip` | Pacote de widget para sincronização |
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

## Onde está a pasta do pendrive?

**A pasta `release/` não aparece no GitHub de propósito:** ela está no `.gitignore` porque contém arquivos gerados com o IPv4 local do computador. Portanto, só aparece **na cópia local do projeto, depois de executar** `start_ktv.bat`, `preparar_pendrive.bat` ou o gerador Python. Não procure o arquivo em `github.com` nem use um ZIP gerado para outro IP.

Passo mais fácil no Windows:

1. Abra a pasta local onde você clonou o KTV.
2. Clique duas vezes em **`preparar_pendrive.bat`**. O Explorador de Arquivos abrirá automaticamente `KTV\release\usb`.
3. Copie a **pasta `userwidget`** que está lá para a **raiz de um pendrive FAT32**, mantendo o ZIP dentro dela, sem extrair.
4. Mantenha `start_ktv.bat` (o servidor) aberto enquanto testa o aplicativo. O PC e a TV precisam estar na mesma rede.
5. Não use o menu "Atualização de Software" da Samsung para esse ZIP: ele é um aplicativo, não firmware.

Se o computador tiver mais de uma rede ou o IP estiver incorreto, confira o IPv4 no `ipconfig` e execute no Prompt de Comando: `preparar_pendrive.bat --ip SEU_IPV4`. O IPv4 deve corresponder ao endereço que o servidor anuncia no terminal. Um IP incorreto pode fazer o aplicativo abrir sem conectar.

Saída esperada:

```text
KTV/
└── release/
    └── usb/
        └── userwidget/
            └── KTV_0.2.0_BR_20261017.zip
```

Se essa pasta não for criada, olhe o erro na janela do script: Python não encontrado, falha no gerador ou servidor não iniciado. **USB Orsay não é uma instalação oficialmente garantida na UN43J5200AG firmware 1080**; a TV pode ignorar esse pacote sem assinatura Samsung.

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
