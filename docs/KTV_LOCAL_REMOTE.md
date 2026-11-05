# KTV Local Remote + Virtual Mouse (MVP)

O serviço de controle remoto é complementar ao teclado, mouse, gamepads e controles físicos. Não altera nem captura os dispositivos existentes.

## Funcionamento

- `remote_server.py`: HTTP + WebSocket na porta TCP 8765, ligado à rede local.
- `remote-web/`: touchpad, D-pad e envio de texto pelo navegador.
- `evdev/uinput`: cria o dispositivo Linux **KTV Virtual Mouse**; movimentos, cliques, scroll e teclas são eventos de entrada do kernel.
- PIN de 6 dígitos no primeiro pareamento; token aleatório persistido em `~/.config/ktv-os/remote.json` (permissão 0600).
- A sessão Linux Live inicia o serviço junto com o KTV. Logs e PIN ficam em `~/.config/ktv-os/remote.log`.
- Porta 8765; abrir `http://IP-DA-TV:8765` em outro dispositivo conectado ao mesmo Wi-Fi/LAN.

## Preparação do sistema

A imagem ARM64 instala `python3-aiohttp` e `python3-evdev`, carrega módulo `uinput` e configura o nó `/dev/uinput` para grupo `input`. A sessão adiciona o usuário `user` ao grupo `input`.

## Segurança / limites do MVP

- O servidor recusa IPs não privados/loopback e requer PIN no pareamento + token no WebSocket.
- **Somente rede confiável**: esta primeira versão usa HTTP/WS sem TLS. Não encaminhe a porta 8765 ao roteador nem use Wi-Fi público.
- O PIN pode ser consultado no log local `remote.log`; a próxima etapa de UX é exibi-lo como QR/PIN dentro da tela KTV e permitir revogar dispositivos.
- O envio de texto MVP cobre letras minúsculas e números; layout/acentos/Shift e teclado completo serão refinados em etapa posterior.
- Mouse virtual requer Linux com `uinput`, permissões e sessão gráfica Xorg/Wayland ativa. Em Windows/macOS o servidor pode mostrar a interface, mas não emular input Linux.
- Não é controle CEC/IR nem controle de TV Samsung: injeta mouse/teclado no próprio KTV OS.

## Execução manual (Linux)

```bash
python3 -m pip install aiohttp evdev
sudo modprobe uinput
sudo usermod -aG input "$USER"
python3 ktv-os/remote_server.py
```

Após adicionar o grupo, faça logout/login. Em produção use a configuração udev da imagem ARM64.
