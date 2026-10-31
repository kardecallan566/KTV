# KTV OS ARM64 — imagem inicializável para Raspberry Pi

Este perfil gera imagens de disco ARM64 do **KTV OS que já existe no repositório**. Ele não cria uma interface paralela: copia o backend Python, a aplicação web, o player e a sessão kiosk atuais para uma imagem Raspberry Pi OS/Debian Trixie.

## Alvos

- Raspberry Pi 3 Model B / Model B+ — `ktv-os-arm64-pi3`
- Raspberry Pi 4 — `ktv-os-arm64-pi4`
- Raspberry Pi 5 — `ktv-os-arm64-pi5`

Cada placa recebe uma imagem específica porque bootloader, firmware e camadas de dispositivo precisam corresponder ao hardware. Para o Raspberry Pi 3, o perfil usa a camada oficial `rpi3`.

## Build local

O construtor utilizado é o [rpi-image-gen](https://github.com/raspberrypi/rpi-image-gen), mantido pela Raspberry Pi.

1. Prepare um host ARM64 Debian/Raspberry Pi OS compatível com a versão do construtor.
2. Clone o rpi-image-gen na versão fixada pelo workflow.
3. Instale as dependências com `sudo ./install_deps.sh`.
4. Execute o perfil correspondente:

```bash
./rpi-image-gen build -S "$PWD/ktv-os/arm64-image" \
  -c config/ktv-os-pi3.yaml
```

Para Raspberry Pi 4 ou 5, substitua o nome do arquivo por `ktv-os-pi4.yaml` ou `ktv-os-pi5.yaml`.

## GitHub Actions

O workflow `.github/workflows/build-ktv-os-arm64.yml` constrói as imagens Pi 3, Pi 4 e Pi 5 em runners ARM64 e publica os arquivos como Actions Artifacts.

Arquivos esperados por placa:

- `KTV-OS-ARM64-pi3.img.xz` e `KTV-OS-ARM64-pi3.img.xz.sha256`
- `KTV-OS-ARM64-pi4.img.xz` e `KTV-OS-ARM64-pi4.img.xz.sha256`
- `KTV-OS-ARM64-pi5.img.xz` e `KTV-OS-ARM64-pi5.img.xz.sha256`

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
2. Extraia o ZIP do artifact e depois extraia o `.img.xz` usando 7-Zip.
3. Abra o Rufus, selecione o pendrive ou microSD correto e escolha o arquivo `.img`.
4. Grave em modo DD, se o Rufus solicitar.
5. Conecte o dispositivo ao Raspberry Pi e à TV por HDMI.
6. Ligue a placa.

A gravação apaga o dispositivo selecionado. Não formate manualmente as partições Linux se o Windows solicitar isso depois da gravação.

### Boot por USB no Raspberry Pi 3 Model B

O Raspberry Pi 3 Model B original (não B+) precisa ter o modo de boot USB habilitado uma única vez. Isso grava um bit permanente no OTP da placa. O procedimento deve ser feito usando um microSD temporário com Raspberry Pi OS:

1. Inicie o Raspberry Pi 3 pelo microSD com Raspberry Pi OS.
2. Edite `/boot/firmware/config.txt` (em instalações antigas, o arquivo pode estar em `/boot/config.txt`).
3. Adicione a linha `program_usb_boot_mode=1`.
4. Reinicie a placa pelo microSD.
5. No terminal, confira com `vcgencmd otp_dump | grep 17:`. O valor esperado após a programação é `17:3020000a`.
6. Remova a linha `program_usb_boot_mode=1` do arquivo e desligue completamente a placa.
7. Retire o microSD, conecte o pendrive com a imagem Pi 3 e ligue novamente.

**Atenção:** a gravação do OTP é irreversível. Faça esse procedimento somente quando estiver pronto para habilitar o boot USB. O boot por armazenamento USB no Pi 3 é experimental e alguns pendrives podem não ser compatíveis; se não iniciar, teste outro pendrive ou use microSD.

## Limites da primeira imagem

O sucesso do GitHub Actions confirma que a imagem foi gerada e que o checksum corresponde ao arquivo publicado. Isso não substitui o teste físico na placa. Ainda precisam ser verificados no Raspberry Pi real:

- boot USB e HDMI;
- autologin e abertura do KTV em fullscreen;
- navegação por controle remoto/teclado;
- rede e áudio;
- reprodução MPV e decoder realmente utilizado;
- desempenho, temperatura e estabilidade contínua.

O Raspberry Pi 3 Model B tem recursos mais limitados que Pi 4 e Pi 5. Chromium em modo kiosk e reprodução de mídia precisam de validação prática; não considerar aceleração de vídeo, CEC ou todos os codecs como garantidos até esses testes físicos serem concluídos.

A imagem é específica para Raspberry Pi e não é uma ISO de PC x86.
