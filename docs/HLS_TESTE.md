# KTV 0.4 — Teste experimental de TV ao vivo HLS (Samsung Legacy/Orsay)

## Por que usar sinal próprio primeiro?

O app Samsung J5200 instalado confirmou contato com o servidor local, mas não demonstrou ainda vídeo HLS funcionando. Para isolar codec, rede e API de reprodução, gere um sinal de teste local com FFmpeg, em vez de depender de streams de terceiros.

## Passos (Windows)

1. Atualize o repositório: `git pull origin main`.
2. Pare e reinicie o servidor: `python installer-local/server.py`. Ele gera `KTV_0.4.1_BR_20261018.zip`.
3. Em outro terminal, dentro de KTV, execute `gerar_hls_teste.bat` (precisa de FFmpeg com `libx264` e `aac`). Mantenha os dois terminais abertos.
4. No navegador do PC, verifique `http://192.168.1.10/hls/demo.m3u8` e os arquivos `.ts` referenciados; troque IP conforme o terminal.
5. No painel `/admin/` seção **TV ao vivo**, cadastre `Teste HLS local` e o endereço `http://192.168.1.10/hls/demo.m3u8` (ajuste IP e porta). Clique em **Assistir**.
6. Faça nova **User App Sync** no Smart Hub, pois é preciso instalar o widget v0.4. Entre no KTV Local instalado, não no WebBrowser.
7. Confira na TV imagem colorida de teste e tom de 440 Hz. Registre os eventos `hls-start-requested`, `hls-buffering`, `hls-buffer-complete` ou `hls-error`. O evento `hls-start-requested` **não** confirma reprodução visual.

O sinal de teste do FFmpeg é gerado localmente; o servidor não faz proxy de canais de terceiros, não converte DRM nem contorna restrições de acesso. Teste apenas transmissões autorizadas. O acesso HTTPS pode falhar no TLS antigo da J5200, mesmo quando a URL funciona no PC.

## Design do player

- Na Samsung Legacy, tentamos o plugin `SAMSUNG-INFOLINK-PLAYER` com `Play(url + "|COMPONENT=HLS")`, segundo a documentação de migração da Samsung; comportamento do firmware 1080 ainda não está comprovado.
- No preview de navegador, tentamos o elemento HTML5 `video`, que **não** equivale a suporte HLS confiável.
- Se não reproduzir, não faça downgrade de firmware. Envie logs e podemos testar a alternativa **SEF Player**, disponível em determinados modelos.
- Limitação atual: reprodução de apenas um canal por vez; cadastro e seleção pelo painel. Guia EPG e favoritos ficam para a próxima etapa.

Referência: https://developer.samsung.com/smarttv/develop/migrating-applications/migrating-legacy-platform-to-toast.html

### Modo seguro na 0.4.1
O KTV aguardará pressionar **ENTER** no controle remoto antes de abrir o player HLS. Primeiro confirme imagem JPG, depois envie o canal pelo Admin e confirme explicitamente pelo controle da Samsung.
