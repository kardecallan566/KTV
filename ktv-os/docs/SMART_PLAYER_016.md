# KTV OS Alpha 0.16 — Smart Player com alternativa oficial

## O que mudou

O Smart Player continua usando o **mpv** para transmissão direta livre, mantendo os modos normal e compatível da Alpha 0.15. Para **canais Pluto TV** e **canais públicos institucionais reconhecidos**, há um botão **Abrir site oficial** no cartão ou no diálogo de reprodução.

Quando o `mpv` encerra ou informa áudio sem saída de vídeo confirmada por três consultas de telemetria, a interface oferece opções para tentar modo compatível ou abrir o site oficial. Esta telemetria **não detecta DRM**: codec, driver, bitrate, rede, expiração de token, autenticação e DRM podem provocar sintomas parecidos.

### Rotas locais
- `GET /api/smart-player/options?kind=pluto&id=<ID>`: retorna se existe opção de site oficial, mas **não** o link de stream nem tokens.
- `POST /api/smart-player/open` com JSON `{"kind":"pluto","id":"<ID>"}` ou `{"kind":"public","id":"tv-brasil"}`: valida identidade e abre uma URL HTTPS *fixa* do site oficial.
- A interface e a API não permitem especificar URL de destino. Canais importados M3U e listas comunitárias não recebem fallback automático para domínios desconhecidos.

Acesso oficial habilitado para o portal da **Pluto TV Brasil**, TV Brasil, Canal Gov, TV Câmara, Canal Educação, TV Cultura e SescTV. O portal Pluto abre a página oficial do serviço, **não necessariamente o mesmo canal em reprodução**; a navegação é realizada pelo usuário no site.

### Navegador e DRM

Para sites oficiais, se o **Google Chrome** já estiver instalado, o KTV OS o prefere. Caso contrário, usa o **Chromium** da ISO. Nada instala o Chrome, Widevine ou quaisquer componentes proprietários automaticamente; não copia ou redistribui bibliotecas DRM nem tenta extrair licenças, sessões ou chaves.

O suporte a reprodução DRM no navegador **não é detectado nem garantido** por essa função. A compatibilidade real depende do navegador instalado, arquitetura, codecs, sistema, região, provedor e login; o site pode negar acesso mesmo no Chrome. A experiência KTV Verde permanece independente.

Em **Raspberry Pi ARM64**, será necessário verificar compatibilidade DRM e suporte a navegador separadamente. Esta ISO continua **amd64** (PC/HDMI).

### Segurança

- Lista finita de URLs oficiais HTTPS no arquivo `smart_player.py`.
- O navegador recebe uma *chave de destino* conhecida, não URL digitada no frontend.
- `kind` e `id` são validados, inclusive Pluto hexadecimal de 24 caracteres e IDs reais do catálogo público.
- Sem baixar manifest, retransmitir streams, automatizar logins, contornar DRM, injetar scripts, mudar políticas de sandbox do Chrome ou expor JWT ao browser.
- A API permanece somente em loopback, exige JSON e valida `Origin` para POST.
- Nenhum erro de reprodução é rotulado como DRM confirmado.

## Testes

```bash
python -m unittest discover -s ktv-os/tests -v
node --check ktv-os/app/app.js
bash ktv-os/linux-live/build-iso.sh --check
```

A ISO esperada é `KTV-OS-Alpha-0.16-amd64.iso` depois do workflow verde na `main`. Testar em hardware real: Pluto no mpv, abrir site oficial, fechar pelo Alt+F4, retornar Alt+Tab, modo compatível, desligar PC/HDMI, rede e controle por mouse. `mpv` pode falhar por causas alheias ao DRM.

Referências:
- https://developers.google.com/widevine/drm/overview
- https://support.google.com/chrome/a/answer/9052345
- https://pluto.tv/br/
