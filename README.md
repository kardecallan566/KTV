# KTV — Samsung Legacy / Orsay local MVP

Protótipo experimental para Samsung **UN43J5200AG (firmware informado: 1080)**. Exibe imagens e vídeos servidos por um computador na mesma rede e aceita comandos por um painel web local.

**Status:** código e testes locais concluídos; **instalação e reprodução ainda não foram confirmadas na TV física**. Não substitui o sistema Samsung. Não utiliza Cloudflare ou GitHub Pages nesta fase.

## Estado atual do projeto

Para consultar o inventário completo do que está implementado, limitações, testes e próximos passos, veja o [Estado e roadmap consolidado do KTV](docs/ESTADO_E_ROADMAP_DO_PROJETO.md). O repositório contém duas linhas separadas: o protótipo Samsung Legacy/Orsay e o KTV OS via PC/HDMI.

## Nova fase: arquitetura multiplataforma

O CP01 (auditoria) está documentado em [docs/ARM64_ARCHITECTURE_PLAN.md](docs/ARM64_ARCHITECTURE_PLAN.md). A trilha Linux ARM64 prioriza o Raspberry Pi 4: o CP02 definiu a arquitetura de referência e o CP03/CP04 criaram contratos Python, diagnóstico somente leitura, adaptador mpv e launcher manual para abrir a UI atual no Chromium. Consulte [docs/MULTIPLATFORM_ARCHITECTURE.md](docs/MULTIPLATFORM_ARCHITECTURE.md) e [docs/ARM64_BUILD.md](docs/ARM64_BUILD.md). A execução no Pi físico, integração do player, serviço systemd, instalador e imagem microSD ainda estão pendentes; a linha AMD64 e o Samsung Legacy/Orsay permanecem preservados.

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


## Recuperacao / teste do Smart Hub (0.4.2)

O pacote 0.4.2 importa a biblioteca `$MANAGER_WIDGET/Common/API/Widget.js` e envia `sendReadyEvent()` antes da primeira requisicao de rede. A sincronizacao LAN agora oferece o **KTV Local** e um aplicativo de diagnostico independente chamado **KTVDiag**. O diagnostico nao usa player de video: se abrir, ajuda a distinguir problemas no KTV principal de falhas gerais do Smart Hub. Consulte [instrucoes de diagnostico](docs/DIAGNOSTICO_INICIALIZACAO.md).


## Diagnóstico pelo WebBrowser da TV

Use `http://IP_DO_PC/tv-info/` no WebBrowser Samsung para obter informações sobre plataforma, resolução e conectividade sem instalar widgets de teste.


## Teste controlado de instalacao de widgets (J5200)

O servidor permite `--sync-only KTV` ou `--sync-only KTVDiag` para sincronizar somente um dos aplicativos mantidos, e `--sync-only reference --reference-zip "CAMINHO_PARA_UM_ZIP_ORSAY_CONFIAVEL"` para testar um ZIP de referência sem recompactá-lo. A lista padrão contém **somente KTV Local e KTVDiag**. Veja [TESTE_REFERENCIA_ORSAY.md](docs/TESTE_REFERENCIA_ORSAY.md).


## KTV 0.4.3 — compatibilidade de inicializacao Orsay

O `config.xml` do aplicativo principal foi refeito com namespace `http://www.samsung.com/` e atributos `itemtype`, a exemplo do projeto Emby/Jellyfin Orsay. Removido XHR no `<head>` antes da chamada `sendReadyEvent()`; o primeiro evento de rede ocorre **depois** do sinal de prontidao. O ZIP e verificado antes de ser publicado (estrutura, icones, CRC e metadados). **Isso nao confirma que o Smart Hub da J5200 conseguira iniciar o aplicativo**. Para testar sem reinstalar os outros diagnosticos, rode `python installer-local/server.py --sync-only KTV`, sincronize no menu develop e confira a abertura do KTV Local 0.4.3. Se continuar falhando, use o ZIP Orsay externo e independente indicado em `docs/TESTE_REFERENCIA_ORSAY.md` antes de qualquer outra alteracao no codigo.


## Limpeza dos widgets de teste descontinuados

Os testes A/B de empacotamento foram encerrados. As pastas de origem correspondentes foram retiradas do repositório; o build remove seus ZIPs antigos de `release/Widget/` e `release/usb/userwidget/` quando reiniciado. A sincronização padrão oferece apenas **KTV Local** e **KTVDiag**. Ícones já instalados na TV devem ser removidos **manualmente no Smart Hub**, pois apagar o ZIP no computador não desinstala aplicativos Samsung.


## Novo projeto — KTV OS (PC conectado à TV por HDMI)

O KTV OS foi iniciado em [ktv-os/](ktv-os/README.md) como projeto separado do antigo widget Samsung. A alpha roda **no computador** (Windows ou Linux), exibe uma interface de televisão por HDMI e já possui navegação por teclado, seções Canais / USB / Entradas / Configurações, servidor localhost e leitura opcional de mídias. **Não é um firmware ou sistema Linux bootável próprio ainda.** A porta USB da Samsung não executa Linux; para um teste via pendrive é necessário inicializar o **PC** por uma imagem Linux Live e conectar o HDMI. Veja [plano KTV OS](ktv-os/docs/ROADMAP.md).

Comandos:

\`\`\`powershell
cd ktv-os
python launcher.py --open
\`\`\`

O servidor Legacy em \`installer-local/\` permanece inalterado.


## KTV OS Linux Live inicializável (Alpha 0.2)

O KTV OS agora conta com [perfil de distribuição Debian Linux Live](ktv-os/linux-live/README.md) para computadores amd64 ligados à TV por HDMI. O construtor gera uma ISO híbrida bootável a partir de Debian 13, com kernel/serviços reais, login gráfico automático e interface KTV em kiosk. Esse sistema executa **no PC ao iniciar pelo pendrive**, sem iniciar Windows. A porta USB da TV Samsung **não instala Linux ou substitui firmware**. A ISO só estará disponível quando a compilação terminar; a saída HDMI/NVIDIA precisa de teste físico.


## KTV OS 0.7 — controle HDMI-CEC experimental

O sistema Linux Live agora pode tentar receber botões de controle remoto da TV via **libCEC**, mediante ativação explícita em Configurações. A saída HDMI do computador não oferece necessariamente CEC; pode ser necessário adaptador USB-CEC. O modo é opcional, não interfere no KTV Orsay e não altera o firmware Samsung. Veja [guia de testes do KTV OS](ktv-os/README.md).
