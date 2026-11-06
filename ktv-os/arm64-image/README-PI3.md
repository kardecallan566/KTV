# KTV OS — imagem para Raspberry Pi 3 Model B

Este ciclo de build tem como alvo exclusivo o Raspberry Pi 3 Model B (1 GB RAM).

## Build automatizado

O workflow `.github/workflows/build-ktv-os-arm64.yml` agora executa somente o perfil `pi3`, usando a layer `rpi3` do `rpi-image-gen`. O artifact esperado contém:

- `KTV-OS-ARM64-pi3.img.xz`
- `KTV-OS-ARM64-pi3.img.xz.sha256`

Artifacts do GitHub Actions expiram após 14 dias. O build concluído não equivale a teste de boot/hardware.

## Limitações e validação

- A placa tem 1 GB RAM; Chromium e reprodução de vídeo podem exigir ajustes de memória e resolução.
- Esta configuração usa Debian Trixie ARM64 minimal como base; compatibilidade de boot, firmware, Wi-Fi/Bluetooth, HDMI, áudio e aceleração de vídeo deve ser verificada no Pi real.
- A imagem ainda é experimental e não deve ser considerada estável até validar boot, interface, rede, áudio e reprodução.
- Não há alegação de teste físico até que o hardware seja efetivamente testado.

## Gravação

Use Raspberry Pi Imager ou ferramenta equivalente, selecionando o arquivo `.img.xz` publicado. Confirme o SHA256 antes de gravar e faça backup do microSD: gravação sobrescreve o conteúdo do cartão.
