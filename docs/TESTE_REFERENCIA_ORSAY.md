# Diagnostico de compatibilidade — Samsung Orsay J5200

## Por que este teste existe

Os quatro aplicativos KTV foram baixados por IP e apareceram no Smart Hub, mas nenhum foi confirmado em funcionamento dentro do ambiente de widget. A pagina `/tv-info/` funcionou no WebBrowser da Samsung (Chromium 25, Linux armv7l). **O WebBrowser e os widgets sao ambientes distintos.** Portanto, precisamos de um aplicativo Orsay independente como controle, em vez de continuar modificando o player.

Uma referencia independente disponivel para teste e o pacote `Jellyfin_2.2.6_Europe_20230928.zip` do repositorio publico `oherau/jellyfin-samsung-orsay-os`, que documenta instalacao em modelos J5200/H. Esse pacote nao e codigo do KTV e nao foi validado na sua TV especifica. Baixe apenas do repositorio original e confira o arquivo antes de usar:

https://github.com/oherau/jellyfin-samsung-orsay-os

O servidor KTV apenas **copia e entrega** os bytes desse ZIP; nao o executa, nao o reempacota e nao o altera. Use-o somente se confiar na fonte. Nao e necessario ter um servidor Jellyfin para observar se o aplicativo chega a abrir a tela inicial.

## Teste A: publicar somente o KTV Local

Pare o servidor e execute, no diretorio KTV:

```powershell
git pull origin main
python installer-local/server.py --sync-only KTV
```

Abra `http://192.168.1.10/widgetlist.xml` no PC. Deve haver apenas um elemento `widget` (`KTV Local`). No Smart Hub da TV, execute **Start User App Sync** no IP 192.168.1.10 e tente abrir **KTV Local**. A URL e o pacote sao os mesmos de antes: esse teste apenas exclui os outros aplicativos da lista de instalacao. O resultado e visual; KTV Local nao faz XHR.

## Teste B: pacote Orsay de referencia, SEM alterar ZIP original

1. Baixe `Jellyfin_2.2.6_Europe_20230928.zip` diretamente do repositorio indicado acima. Salve por exemplo em `D:\KTV\Jellyfin_2.2.6_Europe_20230928.zip`. Nao extraia, nao baixe repositório inteiro no lugar do ZIP de widget.
2. Interrompa o servidor com Ctrl+C e execute:

```powershell
python installer-local/server.py --sync-only reference --reference-zip "D:\KTV\Jellyfin_2.2.6_Europe_20230928.zip"
```

3. Abra `http://192.168.1.10/widgetlist.xml` no PC para conferir que apenas o Jellyfin aparece.
4. Na TV, execute **Start User App Sync**. Verifique se uma nova linha `GET /Widget/Jellyfin_2.2.6_Europe_20230928.zip` aparece como 200.
5. Abra o app Jellyfin instalado. Nao e necessario conecta-lo a um servidor neste teste, apenas observar se o Smart Hub abre a interface inicial e a mantem.
6. Para restaurar a lista padrao do KTV, feche o servidor e execute `python installer-local/server.py` normalmente.

O nome de exibição e o ID do widget sao extraidos do `config.xml` original. O programa exige `index.html` e `config.xml` na raiz do ZIP, inspeciona integridade CRC e rejeita nomes inseguros e tamanhos excessivos.

## Como interpretar

| Resultado | Conclusao |
| --- | --- |
| Jellyfin abre e KTVBare nao | O Smart Hub aceita pelo menos um app Orsay: foco em pacote / HTML / metadados KTV |
| Jellyfin e KTVBare nao abrem | Resultado inconclusivo para defeito no KTV; investigar versao do Smart Hub, armazenamento, conta develop e restricoes deste firmware |
| Jellyfin abre tela inicial mas nao conecta a nenhum servidor | O teste de inicializacao **passou**; a falta de servidor Jellyfin e esperada |
| TV so mostra a tela de carregamento por um tempo e fecha | Nenhum widget chegou a ter abertura confirmada; nao mexer no HLS antes de resolver isso |

## Observacoes de seguranca e privacidade

Nao abrir a porta 80 do roteador para a Internet. Nao divulgar token do painel, MAC ou serial do aparelho. Se o token ja foi compartilhado, pare o servidor, exclua SOMENTE o arquivo `.ktv/admin_token` e reinicie o servidor para gerar outro. Nao altere firmware, menu de servico ou certificados de sistema.

O pacote Jellyfin citado e uma referencia independente de terceiros. Sua procedencia e sua compatibilidade precisam ser verificadas antes do uso. O app pode substituir outro widget com o mesmo ID/nome de pacote ja instalado; faca o teste somente se nao houver Jellyfin/Emby instalado que precise preservar.
