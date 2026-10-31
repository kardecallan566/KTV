# KTV OS ARM64 — imagem para pendrive ou microSD

A versão ARM64 usa o KTV OS existente e uma base Raspberry Pi OS/Debian Trixie. O artefato é uma **imagem de disco `.img.xz`**, não uma ISO x86. Cada placa possui uma imagem própria.

## Baixar a imagem

1. Abra a aba Actions do repositório.
2. Entre na execução do workflow **Build KTV OS Raspberry Pi ARM64 images**.
3. Baixe o artifact correspondente à placa:
   - `KTV-OS-ARM64-pi3` — Raspberry Pi 3 Model B/B+.
   - `KTV-OS-ARM64-pi4` — Raspberry Pi 4.
   - `KTV-OS-ARM64-pi5` — Raspberry Pi 5.
4. Extraia o ZIP do artifact.
5. Extraia o arquivo `.img.xz` com 7-Zip para obter o arquivo `.img`.
6. Opcionalmente, valide o SHA256 no PowerShell:

```powershell
Get-FileHash .\KTV-OS-ARM64-pi3.img -Algorithm SHA256
```

Compare o resultado com o conteúdo do arquivo `.sha256` publicado no mesmo artifact. Ajuste o nome para Pi 4 ou Pi 5 quando necessário.

## Gravar com Rufus

1. Conecte o pendrive ou microSD ao Windows.
2. Abra o Rufus.
3. Selecione cuidadosamente o dispositivo correto.
4. Em seleção de boot, escolha o arquivo `.img` extraído.
5. Inicie a gravação e confirme o modo DD se solicitado.
6. Aguarde a conclusão e ejete o dispositivo com segurança.

**A gravação apaga todo o conteúdo do dispositivo selecionado.** Se o Windows pedir para formatar uma partição Linux depois da gravação, cancele.

## Inicialização por USB

### Raspberry Pi 3 Model B (original, não B+)

O Pi 3 Model B original precisa habilitar o boot USB por meio de uma programação única do OTP. É necessário iniciar primeiro por um microSD temporário com Raspberry Pi OS:

1. Inicie pelo microSD.
2. Edite `/boot/firmware/config.txt` (em instalações antigas, pode ser `/boot/config.txt`).
3. Acrescente `program_usb_boot_mode=1`.
4. Reinicie pelo microSD.
5. Confira no terminal: `vcgencmd otp_dump | grep 17:`. O valor esperado é `17:3020000a`.
6. Remova a linha adicionada do arquivo e desligue a placa.
7. Retire o microSD, conecte o pendrive gravado com a imagem Pi 3 e ligue.

**Importante:** a alteração do OTP é permanente e irreversível. Não execute essa etapa até estar pronto para habilitar o boot USB. O boot USB do Pi 3 é experimental e pode depender do modelo do pendrive. Se não iniciar, experimente outro pendrive ou use microSD.

### Raspberry Pi 4 e Raspberry Pi 5

O boot USB depende da ordem de boot configurada no EEPROM/firmware da placa. Consulte a configuração específica do seu modelo se a inicialização pelo pendrive falhar.

Não use a imagem Pi 3 em Pi 4/5, nem o contrário.

## Estado da validação

O sucesso do GitHub Actions comprova a geração da imagem e a validação do checksum. A compatibilidade final depende do teste físico de boot, HDMI, áudio, rede, controle e reprodução de mídia na placa correspondente. Nenhuma aceleração de vídeo, função CEC ou compatibilidade completa de codecs deve ser considerada garantida antes desses testes.
