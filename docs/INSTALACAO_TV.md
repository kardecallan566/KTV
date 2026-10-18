# Instalação local de KTV na Samsung UN43J5200AG / firmware 1080

**Esta instalação não apaga nem substitui o firmware. É um teste de aplicativo Legacy/Orsay e pode falhar devido a restrições da Samsung.**

## Parte A — testar no PC primeiro

1. Coloque PC e TV na mesma rede local; desligue VPN apenas se interferir nas rotas de LAN.
2. Execute `start_ktv.bat` (ou `py -3 installer-local/server.py --ip 192.168.0.XX`).
3. Abra no PC `http://IP-DO-PC/widgetlist.xml`, confira o endereço e baixe `http://IP-DO-PC/Widget/KTV_0.4.0_BR_20261018.zip`.
4. Abra `http://IP-DO-PC/admin/`, informe o token mostrado no terminal, faça upload de JPG ou PNG, adicione à playlist e salve.
5. Abra `http://IP-DO-PC/preview/`: a imagem deve aparecer após poucos segundos. Se o painel no celular não abrir, teste rede e firewall do Windows.

> Se a máquina tiver duas interfaces (Wi-Fi, VPN, Ethernet, WSL), passe `--ip` com o IPv4 real da LAN exibido por `ipconfig` no Windows. **Não use `127.0.0.1` ou IP do WSL para conectar a TV.**

## Parte B — instalar pela rede local (recomendado testar antes do pendrive)

1. Deixe o servidor KTV aberto na porta **80**. Abra `http://IP-DO-PC/widgetlist.xml` em outro dispositivo na mesma rede, por exemplo no celular.
2. Na Samsung: `Menu > Smart Hub > Conta Samsung` e tente entrar como usuário `develop`, senha `000000` ou em branco, conforme disponível.
3. Abra Smart Hub / Meus Aplicativos. Na linha J5200, relatos da comunidade orientam selecionar um app instalado e **segurar Enter/OK** por alguns segundos.
4. Procure `IP Setting`, informe **só o IP** do computador, como `192.168.1.50` (sem `http://` e sem `:80`).
5. Abra de novo as opções e escolha `Start User App Sync`/sincronização. Aguarde e procure **KTV Local** no Smart Hub.
6. Se aparecer e abrir, mantenha o computador e o servidor ligados e use `http://IP-DO-PC/admin/` para enviar uma imagem e validar o player.

Se a conta develop, o IP Setting ou a sincronização não aparecerem, registre uma foto do menu. Firmware/região podem bloquear o método.

**Atenção:** algumas versões de sincronização removem outros aplicativos de desenvolvedor que foram instalados anteriormente. Registre o que já existe antes de sincronizar.

## Parte C — teste opcional pelo pendrive

1. Com o servidor executado pelo menos uma vez, ele terá criado `release/usb/userwidget/KTV_0.4.0_BR_20261018.zip`.
2. Faça backup do pendrive; formate como FAT32 e **copie a pasta `userwidget` inteira para a raiz**.
3. Coloque o pendrive na TV e veja se o Smart Hub reconhece o aplicativo.
4. Se nada aparecer, não force: teste o método de rede. Algumas instalações Orsay por USB necessitam de assinatura `.sig` da Samsung.
5. **Jamais selecione `Atualização de Software` para esse ZIP.**

## Diagnóstico

| Problema | Checagem |
|---|---|
| Porta 80 em uso | Feche IIS/serviço que ocupa a porta ou confira `netstat -ano \| findstr :80`. Porta 8000 só para testar no navegador. |
| PC abre, TV não conecta | Verifique IP do PC, mesmo roteador/sub-rede, isolamento de clientes Wi-Fi e firewall na rede privada. |
| TV não lista widget | Não confirmar como compatível; anote se o menu de sync existe e se há aviso de assinatura. |
| App abre mas fica offline | Confira IP usado no build. Reinicie servidor e resincronize se IP mudou. |
| Imagem aparece e vídeo não | Primeiro teste vídeo MP4 H.264/AAC curto. Pode exigir implementação futura de plugin player Orsay. |
| Instalador em HTTP porta 80 | Tráfego é local e não criptografado; não exponha à internet/port forwarding. |

Não desligue ou coloque o computador em repouso durante os testes. Uma atualização automática de IP do roteador também pode exigir reconstruir e reinstalar o widget.


## Depois de instalar o KTV no Smart Hub

- Com o app instalado aberto, mantenha o servidor local ativo e abra o painel administrativo.
- A versao 0.3 separa `App Orsay online` de `Preview online` e registra `image-loaded`, `image-error`, `video-ready`, `video-playing` e `video-error`.
- Depois de atualizar o computador, execute outra sincronizacao de aplicativos pelo Smart Hub para instalar a versao nova; atualizar o codigo no PC **nao atualiza automaticamente** o aplicativo instalado.
- Se a TV indicar `image-loaded`, confira na tela se a imagem realmente apareceu. Esse evento sozinho e diagnostico de carregamento.


## HLS experimental — KTV 0.4

Novo canal de teste local, gerado por `gerar_hls_teste.bat` com FFmpeg. Configure uma URL `.m3u8` direta no painel, clique em Assistir e sincronize novamente o widget via User App Sync. Consulte [HLS_TESTE.md](HLS_TESTE.md). A execução no plugin Samsung ainda precisa de teste no hardware real.
