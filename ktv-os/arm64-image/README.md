# KTV OS ARM64 — imagem inicializável para Raspberry Pi

Este perfil gera uma imagem de disco ARM64 do **KTV OS que já existe no repositório**. Ele não cria uma interface paralela: copia o backend Python, a aplicação web, o player e a sessão kiosk atuais para uma imagem Raspberry Pi OS/Debian Trixie.

## Alvos

- Raspberry Pi 4 — `ktv-os-arm64-pi4`
- Raspberry Pi 5 — `ktv-os-arm64-pi5`

Cada placa recebe uma imagem específica porque bootloader, firmware e camadas de dispositivo precisam corresponder ao hardware.

## Build local

O construtor utilizado é o [rpi-image-gen](https://github.com/raspberrypi/rpi-image-gen), mantido pela Raspberry Pi.

1. Prepare um host ARM64 Debian/Raspberry Pi OS compatível com a versão do construtor.
2. Clone o rpi-image-gen na versão fixada pelo workflow.
3. Instale as dependências com `sudo ./install_deps.sh`.
4. Execute:

```bash
./rpi-image-gen build -S "$PWD/ktv-os/arm64-image" \
  -c config/ktv-os-pi4.yaml
```

Para Raspberry Pi 5, use `config/ktv-os-pi5.yaml`.

## GitHub Actions

O workflow `.github/workflows/build-ktv-os-arm64.yml` constrói as imagens Pi 4 e Pi 5 em runners ARM64 e publica os arquivos como Actions Artifacts.

Arquivos esperados:

- `KTV-OS-ARM64-pi4.img.xz`
- `KTV-OS-ARM64-pi4.img.xz.sha256`
- `KTV-OS-ARM64-pi5.img.xz`
- `KTV-OS-ARM64-pi5.img.xz.sha256`

A imagem é compactada em XZ. Extraia o arquivo com 7-Zip antes de selecioná-lo no Rufus; o arquivo extraído terá extensão `.img`.

## O que a imagem configura

- Base Raspberry Pi OS/Debian Trixie ARM64 e camada de boot específica da placa.
- Xorg, LightDM e Openbox.
- Chromium em modo kiosk.
- Python e MPV.
- NetworkManager, áudio, USB, Bluetooth e ferramentas de diagnóstico.
- Código atual de `ktv-os/` instalado em `/opt/ktv-os`.
- Sessão kiosk e tela inicial executadas automaticamente pelo autologin local.

O overlay e o supervisor são reutilizados da distribuição Linux Live existente para manter o comportamento atual do KTV OS.

## Gravação e primeiro boot

1. Baixe o artifact correspondente ao modelo do Raspberry Pi.
2. Extraia o `.img.xz` usando 7-Zip.
3. Abra o Rufus, selecione o pendrive ou microSD correto e escolha o `.img`.
4. Grave a imagem em modo DD, se o Rufus solicitar.
5. Conecte o dispositivo ao Raspberry Pi e à TV por HDMI.
6. Ligue a placa.

A imagem contém o sistema e o KTV OS. Ela não é uma ISO de PC e não deve ser usada em computadores x86.

**USB boot:** a placa precisa estar configurada para iniciar por USB. No Raspberry Pi 4, isso depende também da versão/configuração do EEPROM; no Raspberry Pi 5, confirme a ordem de boot do firmware. Se a placa não iniciar pelo pendrive, valide primeiro a ordem de boot ou teste a mesma imagem em um microSD.

## Limites da primeira imagem

A validação automatizada confirma o build e a estrutura da imagem, mas não substitui o teste físico. Ainda precisam ser verificados no Raspberry Pi real:

- boot USB e HDMI;
- autologin e abertura do KTV em fullscreen;
- navegação por controle remoto/teclado;
- rede e áudio;
- reprodução MPV e decoder realmente utilizado;
- desempenho, temperatura e estabilidade contínua.

Não considerar aceleração de vídeo, CEC ou todos os codecs como garantidos até esses testes físicos serem concluídos.
