# KTV OS no Raspberry Pi OS — Pi 3 Model B

Este método instala o KTV OS **por cima do Raspberry Pi OS**, sem gravar uma imagem própria nem alterar o bootloader. Recomendado para o Raspberry Pi 3 Model B: Raspberry Pi OS **32-bit (armhf)**, instalado em microSD.

## Preparar o Raspberry Pi

1. Grave o Raspberry Pi OS Lite (32-bit) no microSD com Raspberry Pi Imager.
2. No Imager, configure usuário, senha, Wi-Fi e SSH (opcional).
3. Inicie o Pi, conecte à internet e entre no sistema.
4. Instale Git e baixe o projeto:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/kardecallan566/KTV.git
cd KTV
sudo bash ktv-os/raspberry-pi/install.sh
sudo reboot
```

O instalador instala Chromium, MPV, Xorg, Openbox e LightDM; copia o KTV OS para `/opt/ktv-os`; configura login gráfico automático e inicia a interface em kiosk. O sistema base continua sendo Raspberry Pi OS.

## Voltar ao modo terminal / desativar kiosk

Para abrir outro TTY: `Ctrl+Alt+F2` (ou F3). Entre com usuário e senha.

Para desativar o autologin kiosk e voltar ao boot de terminal:

```bash
sudo rm /etc/lightdm/lightdm.conf.d/50-ktv-kiosk.conf
sudo systemctl set-default multi-user.target
sudo reboot
```

Para reativar, execute novamente o instalador e reinicie.

## Notas de hardware e segurança

- O instalador **não formata discos, não altera firmware/EEPROM e não mexe no bootloader**.
- Ele instala pacotes do Raspberry Pi OS e configura o LightDM para login automático no usuário informado.
- O Chromium usa `--disable-dev-shm-usage` para reduzir problemas com a memória compartilhada no Pi 3.
- O Pi 3 tem 1 GB RAM; evite abrir muitas abas ou apps ao mesmo tempo.
- A reprodução de streams depende de codecs, formato e capacidade de decodificação do Pi 3. A aceleração de vídeo não é garantida por este instalador.
- Teste inicial com HDMI, teclado e internet. O desligamento pelo KTV deve ser usado para encerrar com segurança.
- Não exponha a porta 8787 à rede: o backend foi projetado para localhost.
- A primeira instalação e o primeiro boot devem ser feitos com teclado disponível, para recuperação caso o navegador não abra.

## Diagnóstico

- Logs de boot: `journalctl -b`
- LightDM: `journalctl -u lightdm -b`
- Se Chromium não abrir, teste no terminal: `chromium-browser --version`
- O KTV pode ser iniciado manualmente: `cd /opt/ktv-os && python3 launcher.py`

> A instalação foi preparada por scripts e não substitui o teste físico no Pi 3. Compatibilidade de Chromium/MPV, áudio HDMI e desempenho de canais devem ser validados no equipamento.


## KTV OS executado pelo pendrive (sem boot USB)

Neste modo, o Raspberry Pi OS e os programas necessários ficam no microSD. O KTV OS (interface, Python e catálogo do projeto) fica no pendrive. O Pi pode iniciar sem o pendrive; quando ele for conectado, o Openbox detecta a unidade e abre o KTV automaticamente.

### Preparar o pendrive

1. Formate o pendrive em FAT32 ou exFAT (para maior compatibilidade, FAT32; arquivos individuais têm limite de 4 GB).
2. Copie a pasta **ktv-os** deste repositório para a raiz do pendrive. O resultado precisa ser `PENDRIVE/ktv-os/launcher.py` e `PENDRIVE/ktv-os/app/index.html`.
3. No Raspberry Pi OS instalado no microSD, execute o instalador deste repositório uma vez:

```bash
sudo bash ktv-os/raspberry-pi/install.sh
sudo reboot
```

4. Após reiniciar, conecte o pendrive. O KTV abre automaticamente; também funciona se ele já estiver conectado antes de ligar o Pi.

As configurações e favoritos desse modo são gravados em uma pasta oculta `.ktv-config` ao lado de `ktv-os` no pendrive. Não remova a unidade enquanto o KTV estiver gravando. Para encerrar com segurança, desligue o Pi pelo menu do KTV antes de retirar o pendrive.

**Importante:** Python, Chromium, MPV e bibliotecas do sistema continuam instalados no microSD; o pendrive guarda o aplicativo e seus dados. Não é um sistema operacional completo portátil nem um boot direto pelo USB. O instalador configura a sessão para aguardar o KTV USB; sem o pendrive, a tela ficará aguardando.


### Copiar o KTV para o pendrive com um único comando

Com o pendrive conectado e montado no computador Linux, dentro do clone do KTV execute (troque o caminho pelo ponto de montagem real):

```bash
sudo bash ktv-os/raspberry-pi/prepare-usb.sh "/media/$USER/NOME_DO_PENDRIVE"
```

O script confirma antes de copiar, atualiza a pasta `ktv-os` no pendrive e preserva `.ktv-config` (dados e favoritos). **Ele não formata nem particiona o pendrive.** Ao terminar, ejete com segurança e conecte ao Raspberry Pi. Para Windows, copie a pasta `ktv-os` manualmente ou use o WSL com o pendrive montado.


### Preparador automático para Windows

No Windows, use o arquivo **prepare-usb.bat** dentro do projeto baixado/clonado:

1. Baixe o projeto pelo botão **Code → Download ZIP** no GitHub e extraia o ZIP (ou use Git).
2. Conecte o pendrive. Ele pode estar em FAT32 ou exFAT.
3. Abra a pasta extraída e dê dois cliques em `ktv-os/raspberry-pi/prepare-usb.bat`.
4. Digite a letra da unidade do pendrive (por exemplo, `E:`), confira o destino e confirme.
5. Aguarde a cópia terminar e ejete o pendrive com segurança.

O BAT usa Robocopy para sincronizar somente a pasta `ktv-os`; a pasta `.ktv-config` fica separada e é preservada. **Não formata o pendrive.** Execute o BAT a partir do projeto completo extraído, não isoladamente.
