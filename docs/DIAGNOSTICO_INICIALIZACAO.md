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
