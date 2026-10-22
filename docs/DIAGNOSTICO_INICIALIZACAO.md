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


## Diagnostico A/B: KTVBare e KTVFlat (sem reprodução nem rede)

Os logs da v0.4.2 mostram que a TV transferiu KTV e KTVDiag via HTTP 200 mas nao gerou nenhum acesso da aplicacao a API. O KTVDiag exibiu apenas carregamento do Smart Hub e fechou. Isso **nao comprova** falha de instalacao; indica que ainda nao houve execucao de codigo registrada. A referencia Orsay Emby/Jellyfin (https://github.com/Apps2Samsung/Jellyfin-Orsay-App/blob/master/config.xml) usa namespace Samsung e atributos `itemtype`, diferente do XML inicial do KTV.

Criamos dois widgets minimos separados, de identificadores novos, com **o mesmo HTML**, sem CSS externo, sem XHR, sem bibliotecas de video e sem referencia ao servidor. Eles exibem texto imediatamente quando o HTML e aberto e chamam somente `sendReadyEvent()` pelo script Legacy Widget.js.

- **KTVBare:** config.xml com namespace `http://www.samsung.com/` e atributos `itemtype`, alinhado ao app Jellyfin/Emby de referencia.
- **KTVFlat:** mesmo HTML, mas config.xml simplificado semelhante ao KTV original. Comparando os dois, podemos distinguir uma possivel rejeicao do formato XML.

### Testar

1. Pare o servidor, rode `git pull origin main`, inicie `python installer-local/server.py`.
2. Na Samsung, acione uma vez **Start User App Sync**. Os novos ZIPs sao `KTVBare_0.1.0_BR_20261018.zip` e `KTVFlat_0.1.0_BR_20261018.zip`. O KTV principal foi mantido **inalterado** neste checkpoint.
3. Abra **KTVBare**. Observe se aparece a tela de diagnostico e a mensagem de prontidao. Depois abra **KTVFlat**.
4. Ao abrir os dois, **nao havera requisições ao Python**: sao aplicativos offline. A ausencia de logs de execucao nao e prova de falha nesses dois testes; o resultado e **visual**.
5. No **WebBrowser da TV**, acesse `http://192.168.1.10/tv-info/`. Essa pagina mostra User-Agent, tamanho da tela e presenca de APIs. Registra no servidor somente IP e User-Agent informado pelo navegador. Confira `/api/status` no painel administrador, campo `tv_probes`; o log Python exibira `/api/tv-probe` vindo da TV.
6. Para informacoes oficiais: Menu > Suporte > Contato Samsung (nomes variam). Registre modelo completo, versao de software e codigo de modelo; **nao compartilhe numero de serie, MAC ou identificadores pessoais**.

Se ambos os widgets offline falharem, focar Smart Hub, pacote e firmware. Se so KTVBare abrir, priorizar correcoes no XML do app KTV. Se ambos abrirem, isolar o JavaScript e chamadas de rede do KTV em pequenos checkpoints. Nao mexer em firmware ou menu de servico.


## KTV 0.4.3 — alinhamento do manifesto

Comparado o `config.xml` do KTV com o [Emby/Jellyfin Orsay](https://github.com/Apps2Samsung/Jellyfin-Orsay-App/blob/master/config.xml): agora usa o namespace Samsung, `itemtype`, categoria de video e tags de autoria compatíveis. A tela HTML deixa de enviar XHR antes de `sendReadyEvent()`. No `installer-local/build.py`, uma validacao verifica o pacote principal e rejeita arquivos ou metadados ausentes.

**Teste**: `git pull origin main`, depois `python installer-local/server.py --sync-only KTV`. No Smart Hub, faça uma sincronização. O pacote agora será `KTV_0.4.3_BR_20261018.zip`. Verifique se KTV Local abre e mantém tela por 30 segundos. A instalacao de outros aplicativos de desenvolvimento nao é exigida neste checkpoint. Se ainda exibir 'Tente novamente mais tarde', isso é incompatibilidade ainda não resolvida; compare com um ZIP Orsay independente conforme `docs/TESTE_REFERENCIA_ORSAY.md`. Não mexa no firmware.
