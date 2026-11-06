# KTV OS — imagem para Raspberry Pi 3 Model B

Este ciclo de build tem como alvo exclusivo o Raspberry Pi 3 Model B (1 GB RAM).

## Build automatizado

O workflow `.github/workflows/build-ktv-os-arm64.yml` executa somente o perfil `pi3`, usando a layer `rpi3` do `rpi-image-gen`. O artifact esperado contém:

- `KTV-OS-ARM64-pi3.img.xz`
- `KTV-OS-ARM64-pi3.img.xz.sha256`

Artifacts do GitHub Actions expiram após 14 dias. O build concluído não equivale a teste de boot/hardware.

## Recursos existentes no código KTV OS

| Recurso | Estado no código | Observação para Pi 3 |
|---|---|---|
| Interface KTV em modo kiosk | Incluída | Chromium pode consumir boa parte dos 1 GB RAM |
| Navegação por teclado | Incluída | Setas, Enter e Esc dependem do foco/navegador |
| Teclado virtual | Incluído | Matchbox Keyboard; útil para texto/URLs |
| Controle Samsung via HDMI-CEC | Implementado, opcional | Ativar na interface; requer CEC funcional na TV/cabo/driver |
| Controle infravermelho (IR) | Não garantido pela imagem | Necessita receptor IR compatível e configuração adicional; não confundir com CEC |
| Wi-Fi/Bluetooth | Pacotes incluídos | Validar firmware, conexão e reconexão no aparelho |
| Desligamento seguro | API e botão existentes | Validar no hardware antes de uso cotidiano |
| Player MPV | Incluído | Decoder/aceleração e codecs precisam de teste físico |
| Otimização por IA de vídeo | Não é prometida por esta imagem | Melhorias de software não substituem decoder; confirmar implementação e consumo de recursos |

### Como usar o controle remoto

1. Conecte o Pi 3 à TV via HDMI e ligue a TV.
2. Na interface KTV, abra as configurações de controle e ative **recepção CEC**.
3. Use setas, OK/Enter, Voltar/Esc e Início no controle da TV, se o CEC estiver disponível.
4. Se não funcionar, navegue com teclado USB ou teclado/air mouse Bluetooth.

O CEC é uma integração de comandos de navegação, não um receptor infravermelho universal. A opção não deve controlar o power/standby da TV nem trocar entradas HDMI.

## Limitações e validação física pendente

- A placa tem 1 GB RAM; Chromium e reprodução de vídeo podem exigir ajustes de memória e resolução.
- Esta configuração usa Debian Trixie ARM64 minimal; compatibilidade de boot, firmware, Wi-Fi/Bluetooth, HDMI, áudio e aceleração de vídeo deve ser verificada no Pi real.
- A imagem é experimental até validar boot, interface, rede, áudio, controle CEC e reprodução contínua.
- Não há alegação de teste físico até que o hardware seja efetivamente testado.

## Checklist para o primeiro boot

- [ ] Boot pela mídia gravada e autologin
- [ ] KTV abre em tela cheia e navegação funciona
- [ ] Wi-Fi conecta e reconecta
- [ ] HDMI com imagem e áudio
- [ ] Controle CEC (setas, OK, voltar) ou teclado USB/Bluetooth
- [ ] Reprodução MPV: vídeo, áudio, troca de canal e estabilidade
- [ ] Temperatura, memória e funcionamento por pelo menos 30 minutos
- [ ] Desligamento seguro

## Gravação

Use Raspberry Pi Imager ou ferramenta equivalente, selecionando o arquivo `.img.xz` publicado. Confirme o SHA256 antes de gravar e faça backup do microSD: gravação sobrescreve o conteúdo do cartão.
