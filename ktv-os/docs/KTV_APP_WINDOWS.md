# KTV App para Windows

O KTV App é a versão desktop do KTV OS: abre a interface existente em uma janela nativa (WebView), sem lançar o navegador externo. O servidor HTTP é local e fica restrito a 127.0.0.1.

## Executar a partir do código

1. Instale Python 3.10+ no Windows (marque "Add Python to PATH").
2. Na pasta `ktv-os`, execute `install_windows.bat` uma vez.
3. Execute `iniciar_windows.bat`.

## Gerar o executável

Execute `build_windows.bat`. O PyInstaller cria `dist/KTV-App/KTV-App.exe` e os arquivos auxiliares da pasta. Se Inno Setup (`ISCC`) estiver instalado, o script também gera `installer-output/KTV-App-Setup.exe`. Distribua o Setup ou **a pasta completa**, não somente o EXE. O script `windows/KTV-App.iss` define atalhos e instalação por usuário.

## Player

O MPV precisa estar instalado e acessível no PATH do Windows para reprodução nativa de IPTV e vídeos. A interface desktop não substitui o motor de reprodução. O WebView2 Runtime é usado pelo pywebview; Windows 10/11 normalmente já o possui, mas instalações sem ele podem precisar instalar o runtime oficial da Microsoft.

## Dados e segurança

- A interface é servida apenas em `127.0.0.1:8787`; não expõe o servidor KTV à rede.
- Configurações e favoritos ficam no perfil do usuário, em `~/.config/ktv-os` (no Windows, normalmente dentro do perfil HOME).
- O KTV App não altera firmware nem sistema da Samsung. Para HDMI, conecte o PC à TV e selecione a entrada HDMI.
- Este primeiro pacote é um build desktop experimental; o instalador MSI/Setup e distribuição automática ainda são etapas futuras.
