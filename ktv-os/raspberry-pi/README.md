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
