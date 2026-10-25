# KTV OS — Alpha 0.1

Interface de TV para computador conectado a uma televisão por HDMI. Esta pasta **não é ainda uma distribuição Linux, nem um firmware Samsung**. É um *shell* de TV rodando no navegador do computador. Isolado do KTV Orsay em ../tv-orsay/.

## Teste imediato no Windows (PC -> HDMI -> Samsung)

1. Conecte o computador à Samsung por cabo HDMI.
2. No controle da TV, pressione SOURCE e selecione a entrada HDMI do computador.
3. No Windows, pressione Win+P e selecione "Somente segunda tela" ou "Duplicar" conforme sua preferência. Ajuste para 1920x1080 / 60 Hz se disponível.
4. No terminal, a partir da raiz do repositório:
   \`\`\`powershell
   git pull origin main
   cd ktv-os
   python launcher.py --open
   \`\`\`
   Também é possível dar duplo clique em \`ktv-os/iniciar_windows.bat\`.
5. No navegador, pressione F11 para tela cheia. Use setas, Enter e Esc para navegar. Também há botão interno de tela cheia (F).

O servidor fica acessível **somente em http://127.0.0.1:8787/**, no próprio PC. O Windows precisa de Python 3; nenhuma dependência Python adicional.

## Reproduzir arquivos de um pendrive ligado ao computador

Insira o pendrive **no computador** e veja a letra da unidade, por exemplo E:. Inicie:

\`\`\`powershell
python launcher.py --open --media-dir "E:\"
\`\`\`

Por segurança, o KTV OS **só lê arquivos na pasta escolhida**. Na alpha, são suportados arquivos diretamente nessa pasta (não faz varredura recursiva) nos formatos MP4, WebM, MP3, M4A, PNG, JPG/JPEG e GIF. A reprodução depende dos codecs do navegador. O servidor oferece HTTP Range para vídeos.

O recurso **USB da Samsung** não é acessível por um sistema externo conectado por HDMI. Detecção de unidades USB no Windows é apenas informativa: para conceder acesso a mídias, escolha a pasta em \`--media-dir\`.

## Canais personalizados

Na primeira execução, será criado \`~/.config/ktv-os/channels.json\`:

\`\`\`json
{
  "channels": [
    {"name": "Meu canal", "url": "https://meu-servidor.exemplo/live.m3u8", "category": "Pessoal"}
  ]
}
\`\`\`

Edite esse arquivo e entre em "Canais" novamente. Somente URLs HTTP/HTTPS diretas com extensão \`.m3u8\` ou \`.mp4\` são aceitas, e não há links comerciais pré-configurados.

**Limite do MVP:** a lista exibe streams HLS, mas navegadores desktop geralmente não tocam \`.m3u8\` diretamente. A integração com um player nativo ou HLS.js é checkpoint posterior; não confunda cadastro com reprodução.

## TV aberta, HDMI e controle remoto

- **TV aberta:** pressione SOURCE no controle Samsung e selecione TV/Antena. Um eventual sintonizador ISDB-Tb USB no PC exigirá driver e software dedicado.
- **Outras entradas HDMI:** pressione SOURCE na própria TV. O KTV OS externo **não consegue ler outras entradas HDMI da Samsung**; HDMI-CEC e infravermelho são possibilidades a investigar.
- **Controle remoto:** teclado do PC e controles que enviem teclas funcionam no shell. HDMI-CEC do controle Samsung depende de hardware e compatibilidade, não foi implementado ainda.

## Pode rodar diretamente de um pendrive?

**No computador, sim. Na porta USB da Samsung, não.** Para testar sem mexer no Windows, inicialize uma distribuição Linux **Live USB** no PC (opção "Try Ubuntu", sem instalar) e execute o KTV OS nela. A documentação oficial da Canonical explica o procedimento:

https://ubuntu.com/desktop/docs/en/latest/tutorial/try-ubuntu-desktop/

Criar esse pendrive **apaga os arquivos nele**. Faça backup e confira qual unidade está selecionada. Não tente atualizar o firmware da Samsung com a ISO/Linux. Esta alpha não inclui uma imagem bootável própria: o pendrive de Ubuntu é a base experimental; o KTV OS precisa estar acessível nessa sessão, por exemplo em outra mídia, uma cópia local ou clonando o GitHub. Sessões Live sem persistência perdem mudanças ao reiniciar.

### Atenção ao ASUS TUF A15

O notebook com RTX 3050 pode exigir drivers NVIDIA para desempenho e saída HDMI ideais no Linux. O modo Live pode usar drivers abertos e ter limitações. Primeiro teste a imagem na TV; não altere a instalação Windows ou a BIOS sem necessidade.

## Estrutura

- \`app/\`: interface TV 1080p responsiva, navegação teclado.
- \`launcher.py\`: servidor HTTP local, catálogo de canais, biblioteca opcional e estado.
- \`iniciar_windows.bat\` / \`iniciar_linux.sh\`: inicialização em sistema já instalado.
- \`tests/\`: testes automatizados sem dependências externas.

**Segurança:** servidor apenas em loopback; evite abrir porta 8787 para a rede. O diretório \`.ktv-os/\` não entra no Git.

Próximos passos: player Kodi/mpv para HLS e canais, seleção de diretório USB na interface, controle remoto/CEC, hardware para ISDB-Tb, instalação em USB Linux com persistência, depois distribuição Linux KTV dedicada.


## KTV OS Alpha 0.2 — Linux inicializável pelo computador

**Agora existe um perfil de construção de um sistema Linux Live real**, diferente da Alpha 0.1 que roda no navegador do Windows. O Linux Live contém kernel, módulos de hardware, NetworkManager, áudio, LightDM e Openbox, faz login automaticamente na sessão Live e abre a interface KTV OS em tela cheia no Chromium. O Windows não é executado neste processo.

O código e os passos de build estão em [linux-live/README.md](linux-live/README.md). A imagem é criada com `live-build` sobre Debian 13, gerando uma ISO híbrida para pendrive ligado ao **computador**. Os arquivos de configuração ficam em `~/.config/ktv-os/channels.json` (no Live, temporário, sem persistência neste checkpoint).

**Atenção:** não coloque a ISO na porta USB da Samsung, não use o menu Atualização de Software da TV e não substitua o firmware original. O HD/SSD do computador não será formatado ao executar o Linux Live, mas a gravação da imagem no **pendrive selecionado** apagará os dados dele. Hardware NVIDIA e compatibilidade UEFI precisam ser testados fisicamente.


## KTV OS Alpha 0.3 — reprodução nativa e USB

O SO agora inclui o **mpv** no Linux Live e abre HLS `.m3u8` e MP4 autorizados em janela nativa de tela cheia. Na lista de Canais, selecione o cartão e pressione Enter. O mpv aparece à frente da interface; pressione **Q** na janela do mpv para sair e voltar ao KTV OS. Na interface também existe um botão para interromper reprodução. O backend não aceita URLs arbitrárias enviadas ao player: só índices de canais previamente cadastrados e arquivos autorizados.

No computador Windows, é possível testar instalando `mpv` no PATH; se não estiver instalado, o sistema mostra uma mensagem e mantém o fallback HTML5 para arquivos locais.

A seção USB mostra pendrives montados **no computador**, permitindo abrir os arquivos da raiz, reproduzir vídeos/áudios e visualizar fotos. No Linux Live, `udiskie` cuida da montagem automática via UDisks2. Em Windows, as unidades removíveis aparecem por letra. Não são acessadas unidades ligadas à porta USB da Samsung. Acesso é apenas leitura pela interface.

Ainda não há varredura recursiva de subpastas, playlists M3U completas, controle HDMI-CEC nem sintonizador ISDB-Tb. As alterações em canais feitas no Live sem persistência serão perdidas ao reiniciar.


## Alpha 0.4 — gerenciar canais pela TV

Abra **Canais → Adicionar canal** e preencha nome, URL autorizada `.m3u8`/`.mp4` e categoria. A lista permite assistir, favoritar, editar, mover para cima/baixo e excluir (com confirmação). Use teclado para inserir URLs; a navegação por controle/teclas continua nos botões. As alterações são salvas automaticamente em `~/.config/ktv-os/channels.json`, usando gravação atômica.

Para preservar dados ao reiniciar o Linux Live, conecte um **segundo pendrive de dados** ao computador e abra **Configurações → Backup de canais em pendrive**. Selecione-o, clique em **Salvar backup** e, em outra sessão, **Restaurar backup**. A restauração exige confirmação e substitui a lista atual. O arquivo fica na raiz do pendrive como `KTVOS-channels-backup.json`. Nenhuma unidade é formatada. **Ainda não é persistência automática** no USB do próprio boot; essa função será um checkpoint separado.


## Alpha 0.5 — Persistência segura, controles e recuperação

**Persistência opcional:** no menu Configurações, conecte um *segundo pendrive de dados ao computador* (além do USB usado para iniciar o Linux), escolha a unidade e selecione **Ativar neste pendrive**. A opção cria apenas a pasta oculta `.ktv-os-persistence` nesse pendrive e salva seus canais com gravação atômica; **não formata, particiona, nem escreve no SSD ou firmware da Samsung**. Quando a mesma unidade for encontrada no boot seguinte, os canais serão recuperados automaticamente desde que o perfil Live ainda não possua canais locais. Mais de um dispositivo persistente encontrado impede recuperação automática para evitar confusões. Se a unidade for retirada, as mudanças ficam na sessão e serão sincronizadas ao reconectá-la. Para desativar entre reinicializações, mantenha o pendrive conectado e clique em **Desativar gravação automática**: o marcador é removido, mas a cópia de canais permanece no dispositivo. Proteja o pendrive: o arquivo não é criptografado.

**Controle:** além das setas/Enter/Esc, agora há navegação por gamepad USB/Bluetooth reconhecido pelo navegador do computador: D-pad/analógico para mover, A para escolher, B para voltar e Start para Início. O controle original Samsung por infravermelho **não é um gamepad**; requer adaptador HDMI-CEC ou emissor IR, ainda fora do escopo.

**Recuperação:** a sessão Linux reinicia o Chromium após encerramentos inesperados e, depois de falhas consecutivas, abre uma janela para tentar novamente ou sair ao modo de recuperação. Logs em `~/.config/ktv-os/session.log` e `server.log`; execute `/usr/local/bin/ktv-os-diagnostics` pelo console Linux (Ctrl+Alt+F2) para gerar `~/ktv-os-diagnostics.txt`. Nenhum reset, atualização de firmware ou formatação é executado.


## Alpha 0.6 — ajuste seguro de vídeo HDMI e áudio

A tela **Imagem e som** mostra as saídas HDMI/DisplayPort e as resoluções anunciadas por `xrandr` no computador Linux Live. Para mudar a resolução, selecione um modo e escolha **Testar resolução**: o Linux inicia um contador de 20 segundos, e o sistema restaura o modo anterior automaticamente se não houver confirmação. Essa proteção funciona enquanto o processo do servidor Linux continuar ativo; travamentos de kernel/driver podem impedir a reversão automática. Resoluções não anunciadas pelo monitor são rejeitadas. A alteração vale apenas para a sessão Linux em execução, sem modificar firmware da TV.

Na mesma tela, o KTV OS usa `pactl` para listar saídas PulseAudio (incluindo HDMI quando o driver fornecer), selecionar dispositivo de som, ajustar volume de 0 a 100% e alternar mudo. Tudo é executado no próprio computador, sem shell e sem acesso remoto. Se o hardware não oferecer HDMI/áudio, a interface mostra a indisponibilidade e não simula sucesso. O volume da Samsung pode precisar de ajuste separado com seu controle.

**Importante:** notebook ASUS com gráficos híbridos NVIDIA pode não anunciar a saída HDMI pelo driver aberto do Linux Live. O diagnóstico serve para identificar essa situação; resolução e áudio dependem de testes físicos. Não é controle HDMI-CEC das entradas da Samsung nem acesso ao sintonizador interno da TV.


## KTV OS Alpha 0.7 — controle HDMI-CEC opcional

O Linux Live agora inclui `cec-utils` e o módulo `cec_bridge.py`. Em **Configurações → Controle remoto HDMI-CEC**, selecione *Verificar suporte* e *Ativar recepção CEC*. Isso inicia libCEC sob demanda e permite receber apenas as teclas **setas, OK, voltar, início**, encaminhadas para a interface local. Não há envio de comandos para desligar, ligar, alterar volume ou trocar fontes da Samsung; o libCEC pode anunciar um dispositivo de reprodução quando se conecta.

**Atenção:** a maioria dos computadores HDMI x86, incluindo notebooks com NVIDIA, não oferece canal CEC diretamente. Nesse caso, usar um **adaptador USB-CEC compatível**, conectado ao PC e inserido no caminho HDMI, pode ser necessário. Instalar o pacote libCEC não adiciona CEC ao HDMI fisicamente. O botão de diagnóstico informa ausência ou falha de inicialização. Teclado/gamepad continuam funcionando. O controle Samsung por infravermelho não vira automaticamente um joystick USB.

Esta Alpha inclui código e testes simulados para análise de mensagens CEC; não foi testada em adaptador físico. A imagem 0.7 só é válida após GitHub Actions compilar ISO, verificar SHA256 e publicar o arquivo.


## Alpha 0.8 — Internet, espelhamento HDMI, autoinicialização e canais públicos

**Rede:** na aba *Internet e Wi-Fi*, o KTV OS usa o NetworkManager para mostrar interfaces Ethernet e Wi-Fi, pesquisar SSIDs e conectar mediante senha. Cabo Ethernet obtém configuração automaticamente conforme seu roteador. A senha Wi-Fi segue via entrada padrão do `nmcli --ask` e não aparece em argumentos ou respostas HTTP. Redes de portal cativo, 802.1X e SSIDs ocultos ainda podem exigir configuração manual em terminal, por exemplo `nmtui`. **No Debian Live a senha e o perfil de Wi-Fi não sobrevivem a um reboot sem persistência de sistema completo**; o pendrive de persistência de canais NÃO guarda credenciais Wi-Fi.

**HDMI:** o `display_layout.py` usa `xrandr` antes do quiosque para detectar uma saída HDMI e o painel interno. Se houver resolução comum, ambas usam a mesma origem visual e a televisão se torna o monitor principal, evitando extensão da área de trabalho. Se não houver modo comum, ele preserva o layout original como medida de segurança e deixa o diagnóstico no `~/.config/ktv-os/session.log`. Se não houver HDMI, preserva a tela do computador. Alterações aplicadas em **Imagem e som** continuam disponíveis por sessão.

**Boot:** os templates Syslinux/ISOLINUX e GRUB EFI são configurados para entrar no sistema Live padrão após **3 segundos**, sem esperar uma escolha indefinidamente. O menu continua acessível nesse intervalo para recuperação. O hook de chroot configura `graphical.target`, habilita LightDM e NetworkManager. Se o Xorg/driver falhar, o Linux pode continuar no terminal: consulte `systemctl status lightdm` e os logs. A configuração não escreve no SSD/BIOS.

**Canais públicos:** TV Brasil e Canal Gov (endpoints HTTPS institucionais EBC) e TV Câmara (endpoint HTTPS institucional Câmara). Os links são fixos e vinculados a uma lista restrita de domínios; clicar em Assistir aciona apenas uma fonte cadastrada no código, sem aceitar URL arbitrária enviada pelo navegador. A procedência institucional do host foi verificada; **a disponibilidade da transmissão real, o codec, o licenciamento para cada tipo de uso e a segurança total do conteúdo de terceiros não foram comprovados**. Nenhuma IPTV comercial/pirata foi adicionada; essas sugestões são experimentais e podem mudar. O usuário pode adicionar os canais a sua lista pessoal se desejar. No sistema Linux, a reprodução é feita com mpv/HLS e requer internet.

**Limitações:** não substitui o sintonizador ISDB-Tb da Samsung, não converte hardware ARM em x86-64 e não salva senhas de Wi-Fi na USB de canais. Teste HDMI, Wi-Fi, drivers e reprodução com sua TV física antes de tratar a Alpha como produto estável.


## Alpha 0.8 — refinamentos de desligamento e HDMI (sem troca de versão)

- O topo da interface agora traz **⏻ Desligar**, que exige confirmação explícita antes de solicitar `systemctl poweroff` pela sessão Linux Live via logind/polkit. A ação é bloqueada fora do quiosque Live (por exemplo ao abrir `launcher.py` no Windows) e não executa shell ou sudo. Não desliga a TV Samsung automaticamente. Quando a política do Linux não permite desligamento, consulte `/api/system/status` e logs da sessão.
- Removido o botão **Tela cheia** e o atalho F, pois o navegador do sistema abre em modo `--kiosk` por padrão.
- **Imagem e som → Organização das telas:** escolher **Espelhar** para duplicar exatamente a imagem HDMI no painel do notebook, ou **Usar somente a TV** para tornar HDMI primário e desligar outras saídas de vídeo do X11. Ambos são testes temporários por 20 s e só ficam ativos após confirmar. O servidor guarda resolução, posição, primariedade e estado ligado/desligado das saídas conectadas e tenta recuperar o layout anterior após timeout ou Cancelar. A alteração é da sessão atual, sem tocar na BIOS/TV. Não garante recuperação se o driver gráfico ou processo Linux travar.
- O diagnóstico `/api/hardware` agora informa os monitores conectados, a resolução e as coordenadas visíveis para identificar um desktop estendido. Na inicialização, o Linux tenta o espelhamento se ambas as telas anunciarem um modo comum; se não houver, deixa a tela de recuperação acessível.
- **IA:** planejamento isolado em [AI_ASSISTANT_PLAN.md](docs/AI_ASSISTANT_PLAN.md); nenhum peso/modelo foi embutido no boot. Recomendada arquitetura híbrida de comandos locais determinísticos e modelo GGUF pequeno opcional.

### Teste sugerido com a Samsung

1. Com HDMI conectado, abrir **Imagem e som** e escolher a saída HDMI correta (`HDMI-1`, `HDMI-A-0` etc).
2. Selecionar **Espelhar notebook e TV**, testar e confirmar **somente se a imagem estiver visível**.
3. Se ainda existir área estendida, tentar **Usar somente a TV HDMI**, confirmar apenas depois de verificar a imagem. Sem confirmação, a configuração anterior deverá retornar em cerca de 20 segundos.
4. Se a tela ficar preta persistentemente, recuperar no console `Ctrl+Alt+F2` e coletar `xrandr --query`, `systemctl status lightdm` e `ktv-os-diagnostics` antes de repetir.
