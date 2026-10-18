# KTV 0.4.1 — Diagnóstico de encerramento no Smart Hub

A Samsung J5200 (firmware 1080) acessou `/api/state` e solicitou o ZIP, mas o usuário relatou carregamento seguido de retorno à TV aberta. Isso pode ocorrer por widget antigo, inicialização da mídia, problemas de renderização/firmware ou outros motivos ainda não confirmados.

## Correções e hipóteses

1. A versão interna do widget (config.xml) foi atualizada de 0.300 para **0.401**, acompanhando o novo pacote **KTV_0.4.1_BR_20261018.zip**. Esse desencontro pode atrapalhar atualização, mas não está demonstrado como causa.
2. O elemento nativo Samsung HLS e o elemento HTML5 video **não são mais criados na abertura do aplicativo**. Ambos são criados somente depois de um pressionamento de ENTER na mídia correspondente.
3. O player registra evento `app-start` durante a abertura e `hls-deferred` ao aguardar teste de canal. A requisição de estado do widget novo contém `client=orsay`. Sem isso, provavelmente ainda há um player antigo executando (ou outro cliente usando a API).
4. `window.onerror` relata erros JavaScript quando a API do aparelho permitir; não captura falhas nativas que encerrem o processo.

## Como testar

- Pare o servidor (Ctrl+C), `git pull origin main` e inicie `python installer-local/server.py`.
- No PC, veja `http://192.168.1.10/widgetlist.xml`: o download precisa citar o pacote **0.4.1**.
- Na Samsung, use **Start User App Sync** para atualizar o widget. Não use atualização de firmware nem reinstalação por pendrive.
- Antes do teste, no painel `/admin/`, clique em **Limpar reprodução**, evitando uma mídia problemática do estado persistido.
- Abra o **KTV Local no Smart Hub** (não o WebBrowser) e espere uns 20 segundos.
- O terminal deve mostrar `/api/event?client=orsay&event=html-start`, depois `/api/event?client=orsay&event=app-start` e `/api/state?client=orsay...` (ordem variável). O HUD do widget deve indicar **LOCAL 0.4.1**.
- Envie uma imagem JPG pequena, adicione à playlist e salve. A foto deve aparecer sem precisar pressionar Enter.
- Só se a imagem funcionar, cadastre o HLS local, clique Assistir e **pressione ENTER na TV** para iniciar o teste de vídeo. Se o aplicativo fechar somente após ENTER, a API de mídia é o principal suspeito.

Se o app não abrir ou só aparecer requisição sem `client=orsay`, faça uma foto da lista de aplicativos/versão no Smart Hub, confira se o widget foi realmente substituído. Em caso de conflito de versão, remover só o app KTV de desenvolvedor e sincronizar de novo pode ser um teste, mas não redefina o Smart Hub e não mexa nos outros aplicativos.

Não poste o token do painel. Use LAN confiável; nunca expor HTTP porta 80 à internet.


## Checkpoint 0.4.2 — confirmação do gerenciador Samsung

A TV baixou o pacote 0.4.1 (`GET /Widget/KTV_0.4.1...zip 200`), mas nao fez nenhuma chamada `client=orsay` apos iniciar o Smart Hub. Foi detectada ausencia da biblioteca `Widget.js`, que fornece `sendReadyEvent()`, chamada na documentacao Samsung Legacy para notificar que o app esta pronto. A v0.4.2 importa esta biblioteca e faz a notificacao **antes de consultar a API**. Isto e uma correcao concreta; a causa exata da mensagem do Smart Hub ainda nao foi provada.

### Procedimento isolado

1. Pare Python com Ctrl+C, atualize via `git pull origin main` e inicie `python installer-local/server.py`.
2. Confira em `http://192.168.1.10/widgetlist.xml` a existencia dos itens `KTV Local` (0.4.2) e `KTVDiag` (0.1).
3. Faca `Start User App Sync` no Smart Hub. Verifique se o terminal registra **dois** downloads distintos em `/Widget/`. Se vier so um, anote qual.
4. No Smart Hub, abra **KTVDiag** primeiro. Ele **nao abre video**: mostra uma tela azul com `KTV DIAGNOSTICO`, o estado da biblioteca Samsung, a conectividade e um teste de ENTER. O servidor deve mostrar `192.168.1.42 GET /api/health?client=diagnostic&ts=...`.
5. Se o KTVDiag abrir, abra KTV Local 0.4.2 com playlist vazia e aguarde 30 segundos. Se funcionar, teste JPG e somente depois HLS.
6. Se ambos exibirem `Tente novamente mais tarde`, pode ser um problema do Smart Hub, da instalacao ou de um requisito de pacote. Nao significa que o HLS causou a falha. Evite reset de fabrica, firmware ou alteracao de aplicativos existentes.

O ZIP de diagnostico esta em `release/Widget/KTVDiag_0.1.0_BR_20261018.zip`. A TV **nao precisa do pendrive** para o teste, pois a sincronizacao e via LAN.
