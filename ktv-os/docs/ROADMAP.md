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
