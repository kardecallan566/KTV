# KTV OS ARM64 — imagem inicializável para Raspberry Pi 3 Model B

Este perfil gera uma imagem de disco ARM64 do **KTV OS que já existe no repositório**. Ele reutiliza o backend Python, a aplicação web, o player e a sessão kiosk atuais em uma imagem baseada no Raspberry Pi OS/Debian Trixie.

## Hardware-alvo

- **Raspberry Pi 3 Model B** — camada oficial `pi3` do `rpi-image-gen`.
- CPU Broadcom BCM2837 / Cortex-A53 de 64 bits.
- 1 GB de RAM; imagem preparada para o hardware mais limitado da linha.
- Cartão microSD recomendado para a instalação inicial.

O Pi 3 Model B suporta inicialização ARM64. A imagem é específica para o Pi 3 e não deve ser usada em Pi 4/5 nem em computadores x86.

## Build local

O construtor utilizado é o [rpi-image-gen](https://github.com/raspberrypi/rpi-image-gen), mantido pela Raspberry Pi.

1. Prepare um host ARM64 Debian/Raspberry Pi OS compatível com a versão do construtor.
2. Clone o `rpi-image-gen` na versão fixada pelo workflow (`v2.9.0`).
3. Instale as dependências com `sudo ./install_deps.sh`.
4. Execute:

```bash
./rpi-image-gen build -S "$PWD/ktv-os/arm64-image" \
  -c config/ktv-os-pi3.yaml
```

## GitHub Actions

O workflow `.github/workflows/build-ktv-os-iso.yml` gera **duas imagens no mesmo fluxo** quando o KTV OS é atualizado na branch `main` (ou manualmente):

- ISO inicializável `amd64` para computadores.
- Imagem de disco `ARM64` específica para Raspberry Pi 3 Model B.

O job do Raspberry Pi usa runner ARM64, valida a configuração `pi3`, compila a imagem, verifica a estrutura do disco e publica o artefato compactado em XZ.

Arquivo publicado:

- `KTV-OS-Raspberry-Pi-3-Model-B.img.xz`
- `KTV-OS-Raspberry-Pi-3-Model-B.img.xz.sha256`

Os artefatos ficam disponíveis na execução do GitHub Actions por 14 dias. Extraia o `.img.xz` antes de gravar.

## O que a imagem configura

- Base Raspberry Pi OS/Debian Trixie ARM64 e camada de boot específica do Pi 3.
- Xorg, LightDM e Openbox.
- Chromium em modo kiosk.
- Python e MPV.
- NetworkManager, áudio, USB, Bluetooth e ferramentas de diagnóstico.
- Código atual de `ktv-os/` instalado em `/opt/ktv-os`.
- Sessão kiosk e tela inicial executadas automaticamente pelo autologin local.

O overlay e o supervisor são reutilizados da distribuição Linux Live existente para manter o comportamento atual do KTV OS.

## Gravação no microSD

1. Abra o artifact `KTV-OS-Raspberry-Pi-3-Model-B` na execução do GitHub Actions.
2. Baixe `KTV-OS-Raspberry-Pi-3-Model-B.img.xz` e extraia o arquivo `.img` com 7-Zip ou ferramenta equivalente.
3. Abra o Raspberry Pi Imager, escolha **Use Custom** e selecione o arquivo `.img` extraído.
4. Selecione o cartão microSD correto e grave a imagem.
5. Insira o cartão no Raspberry Pi 3 Model B, conecte HDMI, teclado/controle e rede, e ligue a placa.

**Atenção:** a imagem é um disco para microSD, não uma ISO para Rufus/Ventoy. Faça backup do cartão escolhido, pois a gravação apaga seu conteúdo.

## Limites da validação

A compilação automatizada e a verificação do arquivo confirmam que a imagem foi construída, mas não substituem o teste no hardware real. Ainda precisam ser verificados no Raspberry Pi 3 Model B:

- boot pelo microSD e saída HDMI;
- autologin e abertura do KTV em fullscreen;
- navegação por controle remoto/teclado;
- Wi-Fi, Ethernet e áudio;
- reprodução MPV e decoder realmente utilizado;
- desempenho com 1 GB de RAM, temperatura e estabilidade contínua.

A aceleração de vídeo, CEC e todos os codecs não devem ser considerados garantidos até esses testes físicos.
