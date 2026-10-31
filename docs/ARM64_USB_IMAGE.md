# KTV OS ARM64 — imagem para pendrive ou microSD

A versão ARM64 usa o KTV OS existente e uma base de boot Raspberry Pi OS/Debian Trixie. O artefato é uma **imagem de disco `.img.xz`**, não uma ISO x86.

## Baixar a imagem

1. Abra a aba Actions do repositório.
2. Entre na execução do workflow **Build KTV OS Raspberry Pi ARM64 images**.
3. Baixe o artifact correspondente ao modelo da placa: `KTV-OS-ARM64-pi4` ou `KTV-OS-ARM64-pi5`.
4. Extraia o ZIP do artifact.
5. Extraia o arquivo `.img.xz` com 7-Zip para obter o arquivo `.img`.
6. Opcionalmente, valide o checksum com:

```powershell
Get-FileHash .\KTV-OS-ARM64-pi4.img -Algorithm SHA256
```

Compare o resultado com o checksum publicado. Para Pi 5, use o nome correspondente.

## Gravar com Rufus

1. Conecte o pendrive ou microSD ao Windows.
2. Abra o Rufus.
3. Selecione cuidadosamente o dispositivo correto.
4. Em seleção de boot, escolha o arquivo `.img` extraído.
5. Inicie a gravação e confirme o modo DD se solicitado.
6. Aguarde a conclusão e ejete o dispositivo com segurança.

**A gravação apaga o conteúdo do dispositivo selecionado.**

## Iniciar no Raspberry Pi

Conecte o dispositivo gravado, HDMI e alimentação. O boot por USB depende da ordem de boot configurada no firmware da placa. Caso não inicie pelo pendrive, use um microSD para diagnóstico ou ajuste a ordem de boot conforme o modelo.

A primeira versão tem imagens específicas para Raspberry Pi 4 e Raspberry Pi 5. Não use a imagem de um modelo no outro.

## Estado da validação

O sucesso do GitHub Actions comprova a geração e a integridade estrutural da imagem. A compatibilidade final depende do teste físico de boot, HDMI, áudio, rede, controle e reprodução de mídia na placa correspondente.
