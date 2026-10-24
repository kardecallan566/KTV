# KTV OS Alpha 0.2 — Distribuição Linux Live para PC/HDMI

Esta etapa é **um sistema operacional Linux inicializável de verdade** — kernel Linux Debian, drivers de computador, gerenciador de sessões e uma interface KTV OS automaticamente em modo de TV. Não é firmware alternativo para a Samsung. O dispositivo de execução é um computador x86-64, que envia imagem e áudio via HDMI à TV.

## Como funciona o boot

1. O computador inicia a ISO Debian Live pelo pendrive (sem iniciar o Windows).
2. O `live-boot` monta o sistema em memória com escrita temporária.
3. O `live-config` prepara a conta `user` do ambiente Live.
4. O `LightDM` abre automaticamente a sessão `Openbox` nessa conta.
5. O script `ktv-os-session` inicia o servidor Python apenas em `127.0.0.1:8787`, espera o serviço responder e abre o Chromium em tela cheia.

A interface é apenas o frontend: o kernel, Xorg, NetworkManager, serviços de áudio e dispositivos USB funcionam no Linux por baixo dela. A ausência de uma tela inicial proprietária de boot não invalida o fato de que se trata de uma distribuição Linux personalizada.

## Gerar a ISO (Debian 13 x86-64)

Em um sistema Linux Debian 13 com acesso à internet, na raiz do repositório KTV:

```bash
sudo apt update
sudo apt install -y live-build debootstrap xorriso squashfs-tools \
  grub-pc-bin grub-efi-amd64-bin syslinux-utils isolinux mtools dosfstools
bash ktv-os/linux-live/build-iso.sh --check
sudo bash ktv-os/linux-live/build-iso.sh
```

Arquivo esperado: `ktv-os/linux-live/dist/KTV-OS-Alpha-0.2-amd64.iso`. Verificação: arquivo `.sha256` ao lado. Compilação precisa baixar pacotes Debian e pode consumir vários GB de disco; não há necessidade de usar o Windows diretamente para essa etapa. O script não formata nem instala nada nos seus discos: produz apenas um arquivo ISO.

Também existe um fluxo GitHub Actions [**Build KTV OS ISO**](../../.github/workflows/build-ktv-os-iso.yml) para criar um artefato de ISO. Só considere a ISO gerada após o workflow apresentar **success** e o artefato estar disponível; não confundir os arquivos de build com uma ISO compilada.

## Gravar no pendrive com segurança

1. Separe um pendrive **de pelo menos 8 GB** e faça backup: ele será apagado.
2. No Windows, use Rufus ou Ventoy para transferir a ISO ao pendrive. Confira **duas vezes** o dispositivo de destino para não apagar outra unidade.
3. Insira o pendrive no **computador**, não na Samsung.
4. Com o cabo HDMI ligado à televisão, selecione o pendrive no menu de boot do computador. No ASUS TUF, a tecla de seleção de boot frequentemente é Esc, mas pode variar conforme firmware.
5. Se houver menu Live, selecione a inicialização em modo Live. Não selecione instalação no disco.
6. Verifique se aparece a interface KTV OS em tela cheia na TV.

**Não use o atualizador de firmware da Samsung.** O computador pode iniciar o sistema sem apagar o Windows, mas uma ISO escrita na unidade errada apaga os dados dessa unidade.

## Limitações da primeira ISO

- Não há persistência de favoritos, uploads nem configurações após desligamento do Live; será adicionada depois.
- A saída HDMI da NVIDIA RTX 3050 no notebook ASUS pode precisar de drivers especiais; o Live inicial usa drivers Debian livres. Se a tela HDMI ficar preta, precisamos diagnosticar driver/roteamento de GPU — não formatar o computador.
- Canais abertos da antena e demais portas HDMI da Samsung permanecem controlados pelo firmware original. Na interface, a opção TV aberta orienta trocar a fonte com o controle remoto. Um sintonizador ISDB-Tb externo e HDMI-CEC serão etapas posteriores.
- O suporte a HLS `.m3u8` ainda não inclui player nativo. O SO inicializa, mas algumas mídias não serão reproduzidas até integrarmos player adequado.
- USB: drivers e `udisks2` estão incluídos, mas montagem automática e seleção de pastas na interface ainda precisam de desenvolvimento. Não confundir detecção básica com acesso completo a pendrives.
- Início automático ainda precisa ser testado fisicamente em UEFI e na saída HDMI. A compilação bem-sucedida por si só não valida seu notebook.

## Estrutura

- `build-iso.sh`: cria ISO híbrida Debian Live a partir de `live-build`.
- `packages.list.chroot`: pacotes Linux necessários ao sistema.
- `overlay/etc/lightdm/`: login Live automático.
- `overlay/etc/xdg/openbox/`: inicialização da sessão gráfica.
- `overlay/usr/local/bin/ktv-os-session`: servidor KTV OS + navegador kiosk.

O sistema nunca tenta substituir bootloader ou firmware da Samsung.


**Construção automatizada:** o GitHub Actions usa o contêiner oficial `debian:trixie` com permissões de build para evitar incompatibilidades de `live-build` do Ubuntu 24 (a versão anterior tentou acessar um caminho de segurança obsoleto `trixie/updates`). O perfil seleciona explicitamente o espelho `debian-security`. O builder nativo recomendado continua Debian 13.


## Alpha 0.3 — player e montagem USB

Foi adicionado o pacote Debian `mpv` ao sistema Linux e `udiskie` para montar automaticamente volumes removíveis conectados ao computador. A API local restringe a reprodução mpv a canais validados e arquivos do diretório autorizado ou de uma unidade removível montada. A ISO gerada agora usa o nome **KTV-OS-Alpha-0.3-amd64.iso**; ainda é necessário validar fisicamente GPU/HDMI e os codecs da transmissão.


## Alpha 0.4 — canais e backup USB

O arquivo da próxima compilação é **KTV-OS-Alpha-0.4-amd64.iso**. O gerenciador de canais permite cadastrar/editar/reordenar/favoritar pelo teclado e controle. O backup requer **um pendrive de dados separado**, ligado ao PC, montado automaticamente pelo Linux; pelo menu Configurações, selecione a unidade e escolha Salvar backup ou Restaurar backup. Nenhum pendrive é formatado pelo KTV OS. O arquivo na raiz do volume se chama `KTVOS-channels-backup.json`. O Linux Live sem persistência perde alterações não copiadas para USB ao reiniciar. Futuro: persistência automática após testes de hardware.

O workflow de ISO verifica dinamicamente o nome do arquivo e o hash antes de disponibilizar artefatos, evitando que um nome antigo de versão cause falha de publicação.


## 0.5 — Persistência opt-in e recuperação

A ISO contém `persistence.py` e suporte `zenity`/terminal para diagnóstico do boot. Um segundo pendrive montado em `/media/user` ou `/run/media/user` pode guardar `.ktv-os-persistence/device.json` e `channels.json`; o recurso só é habilitado mediante ação explícita no menu Configurações. O KTV OS procura o marcador nas inicializações seguintes e restaura os canais se não houver lista local. Não há modificação de partições, criptografia, nem instalação no SSD do computador. Para desligar a persistência, o pendrive precisa estar conectado, pois o sistema remove somente seu marcador de ativação.

Se o navegador fechar repetidamente, o supervisor fornece um diálogo **Tentar novamente / Sair para diagnóstico**, com logs em `~/.config/ktv-os` e console de recuperação pelo atalho Ctrl+Alt+F2. Isso não garante compatibilidade com todos os drivers Nvidia/HDMI; testes no PC conectado à Samsung continuam indispensáveis.


## KTV OS Alpha 0.6 — saídas HDMI e áudio

Incluídos `hardware.py` e o pacote Debian `pulseaudio-utils` (com `pactl`). O KTV OS exibe saídas conectadas/modes de `xrandr` e sinks PulseAudio na seção Imagem e som. Alterações de resolução são **temporárias até confirmação**; após 20 segundos sem confirmação, o backend tenta restaurar a resolução anterior. Mudanças não são salvas no firmware nem forçam resolução arbitrária, e a proteção depende de o processo Python/Xorg permanecer ativo. O volume e a escolha de saída de áudio são aplicados ao servidor de som da sessão Linux. Driver HDMI/NVIDIA ainda requer teste físico.


## Alpha 0.7 — receptor HDMI-CEC via libCEC

O pacote Debian `cec-utils` fornece `cec-client`. A recepção dos botões é **desativada por padrão** e precisa ser ativada pela interface (Configurações). Apenas eventos de controle `up/down/left/right/select/back/root menu` são enviados à interface Chromium por uma API loopback; nenhum comando de energia ou seleção de fontes é emitido pelo KTV OS. A inicialização de libCEC pode anunciar o novo aparelho no barramento HDMI. **Em notebook PC HDMI pode não haver interface CEC** sem um adaptador USB-CEC compatível. O código NÃO simula suporte físico: a ausência de cec-client é mostrada e um dispositivo não reconhecido faz a sessão de recepção encerrar.

A construção da imagem passa a incluir `cec_bridge.py` e usar o nome `KTV-OS-Alpha-0.7-amd64.iso`. É preciso validar a compilação e testar navegação real com um adaptador apropriado.
