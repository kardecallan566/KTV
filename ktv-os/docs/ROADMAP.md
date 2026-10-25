# Plano do KTV OS

## Princípios
- A Samsung UN43J5200AG permanece com firmware original e atua como tela, alto-falantes e sintonizador próprio.
- O computador atual, ligado por HDMI, fornece CPU/GPU, rede, mídia e interface.
- Um pendrive na TV nunca é tratado como disco de boot; um pendrive **no PC** pode iniciar Linux.
- Sem reempacotar IPTV de assinatura, quebrar DRM ou retransmitir conteúdo sem autorização.

## Entregas
1. **Alpha 0.1 (PC/HDMI):** interface full-screen local, navegação por teclado, status, catálogo editável de streams, USB com pasta explícita, reprodução HTML5 de MP4/imagens, modo seguro em loopback. Não é um kernel/OS próprio.
2. **Alpha 0.2 (player real):** integração nativa com Kodi ou mpv/libVLC (escolha baseada em testes no Windows e no Linux); suporte HLS/M3U e codecs, buffer, erro e reconexão.
3. **Alpha 0.3 (hardware):** detecção USB, permissões e montagem segura; mapa dos botões de controle; CEC/IR se hardware suportar; TV aberta por sintonizador ISDB-Tb externo opcional.
4. **Beta (Linux Live USB):** avaliar base Linux compatível com GPU NVIDIA do ASUS TUF, boot por PC e HDMI, persistência e modo kiosk com login automático. Criar imagem **apenas após** validação da GPU/HDMI e ajustes de drivers.
5. **KTV OS dedicado:** distribuidor de atualizações, backup de favoritos, recuperação, integração do KTV Admin com permissões, e eventualmente hardware externo dedicado.

## Critérios de aceite do MVP
- Executa no Windows em 127.0.0.1:8787 e abre em tela cheia no HDMI.
- Cinco seções navegáveis por setas, Enter e Esc.
- TV aberta/HDMI indicam a limitação e a ação correta no controle Samsung.
- Arquivos somente dentro do diretório indicado pelo usuário.
- Nenhum acesso remoto ou alteração do sistema operacional instalado.
- Testes automatizados verdes no GitHub Actions.

## Limitações técnicas a resolver
- Chromium/Brave desktop não garantem HLS direto; testar mpv/Kodi e selecionar backend.
- HDMI-CEC geralmente exige suporte na porta/adaptador e expõe somente comandos limitados, não transforma HDMI OUT em HDMI IN.
- Drivers de GPU NVIDIA e aceleração por hardware exigem seleção cuidadosa da base Linux.
- USB ISDB-Tb deve ter driver Linux e ser testado com recepção local legal de canais abertos.


## Alpha 0.2 — inicialização USB real

Adicionado construtor de imagem Debian Live amd64 em `ktv-os/linux-live/`, sessão gráfica LightDM/Openbox e kiosk KTV OS iniciado automaticamente sem Windows. O código-fonte passa por testes automáticos de estrutura; uma ISO só pode ser considerada pronta quando o `live-build` finalizar e o arquivo for validado. Persistência, drivers NVIDIA proprietários, rádio ISDB-Tb, HDMI-CEC e entrada HDMI capturada continuam fora do escopo e serão testados separadamente.


## Alpha 0.4 — canais via interface e backup explícito

O usuário pode cadastrar, editar, favoritar, ordenar e remover canais diretamente na interface KTV OS. Um arquivo separado `channel_store.py` valida URL/ID, limita a 100 canais e grava de forma atômica em espaço de usuário. Backup/restauração manual em mídia USB removível montada no computador, com confirmação para substituir a lista existente. A ISO 0.4 inclui o módulo e corrige o workflow para não tentar validar nomes de ISO de versões anteriores. Persistência automatizada e guia EPG permanecem fora do escopo.


## Alpha 0.5 — segurança e UX

Implementada persistência de canais opt-in em pendrive USB removível, com marcador de habilitação, restore automático apenas quando o perfil local ainda não contém dados, sincronização de alterações e desativação persistente sem apagar o snapshot. Controle por gamepad via navegador (USB/Bluetooth no computador), mantendo teclado. Supervisor com recuperação de falhas, logs compactados por sessão e utilitário de diagnóstico read-only. Não altera bootloader, firmware, TV, partições nem arquivos fora da pasta KTV OS em USB escolhido.


## Alpha 0.6 — integração de imagem e som

Diagnóstico de saídas HDMI/DP (xrandr), identificação de modos permitidos pelo monitor, mudança com confirmação/reversão automática após 20 segundos, seleção de saída PulseAudio, ajuste de volume/mudo e mensagens de indisponibilidade para hardware sem driver. Testes simulam execução de xrandr/pactl e a reversão; CI também recompila a imagem Linux Live com o novo módulo.


## Alpha 0.7 — controle remoto CEC

Integração **experimental e opcional** com libCEC para receber eventos de botões (setas/selecionar/voltar/início) via `cec-client`. Requer hardware compatível; PC HDMI normal pode não suportar CEC sem adaptador USB. Habilitação e desabilitação explícitas na tela Configurações, sem autoativação e sem comandos CEC de power/sources. Testes simulados para entrada e validação de eventos; CI gera ISO Debian Live com `cec-utils` incluído. Validação física Samsung ainda necessária.


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
