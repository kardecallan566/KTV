# KTV OS Alpha 0.20 — Pesquisa no Rei dos Canais com importação segura de programação

## O que foi identificado

Em 25/10/2026, o catálogo https://reidoscanais.cam/canais anunciava **104 canais**, incluindo HBO, Telecine, Premiere e outras emissoras por assinatura, além da TV aberta. O site informa que indexa transmissões alojadas por terceiros e publica documentação de API em https://reidoscanais.cam/api, com base anunciada **https://api.reidoscanais.cam**.

A existência da API aberta e a possibilidade técnica de embutir um player não comprovam que o serviço tenha os direitos de retransmissão dos canais pagos ou de outras emissoras. Além disso, a API não respondeu à verificação externa nesta análise. **Não afirmamos que 104 canais foram incorporados nem que a API esteja funcionando.**

## Implementação desta versão

Foi criado o módulo `reidos_guide.py`, que acessa apenas a URL fixa `https://api.reidoscanais.cam/channels` sob demanda, quando a tela Canais é aberta, e interpreta um JSON limitado a 2 MiB e 400 entradas. A fonte é consultada no máximo uma vez a cada cinco minutos durante uso normal; nenhuma requisição ocorre no boot.

Por padrão, somente as informações de **Band, Globo, Record, RedeTV!, SBT, TV Aparecida, TV Brasil e TV Cultura** são selecionadas por nome permitido. Se a fonte trouxer EPG de `current` / `next` com timestamps Unix atuais e títulos seguros, o KTV exibe **Agora / A seguir**. Programas antigos ou sem horários corretos aparecem como indisponíveis.

A tela **Guia complementar da TV aberta** exibe a fonte dos dados e não afirma disponibilidade de vídeo. Onde existe uma transmissão **independente já aprovada no KTV** (TV Brasil, TV Cultura), o cartão pode reproduzir pelo `mpv`. Também pode reproduzir a emissora que o KTV detectou por sintonizador **USB ISDB-Tb local** e a antena do usuário.

Para emissoras sem sinal de antena encontrado nem stream oficial validado, o cartão mostra apenas a programação e explica por que não há botão de reprodução. O conector de terceiros não altera os canais existentes.

## Limites e segurança

- **Nenhum `embed_url`, logo, URL de vídeo, HTML, script, redirecionamento, cookie, token, anúncio ou player do Rei dos Canais é importado ou executado.**
- Somente HTTPS na API fixa, sem redirects HTTP, com timeout curto, limites de tamanho e lista estrita de nomes.
- Os dados recebidos são reduzidos no servidor a título, emissora, horários e ID de reprodução do **próprio KTV**, quando existir. No navegador os nomes aparecem por `textContent`, não HTML dinâmico.
- HBO, Premiere, Telecine e similares não entram nesta integração, pois não há autorização verificável para seus players de terceiros.
- O módulo é somente leitura, não instala extensões, não extrai links e não contorna DRM ou outros controles de serviço.
- Se a API ficar indisponível, mostra aviso e **não impede** que Pluto, canais por antena ou IPTV já configurados funcionem.
- A API pode mudar de formato, de domínio ou desativar o serviço; testes automatizados cobrem JSON simulado, mas o acesso real depende de rede e disponibilidade do host.

## Testes

```bash
python -m unittest discover -s ktv-os/tests -v
node --check ktv-os/app/app.js
bash ktv-os/linux-live/build-iso.sh --check
```

A ISO **KTV-OS-Alpha-0.20-amd64.iso** é voltada a PCs via HDMI. Ainda precisamos de imagem ARM64 própria para Raspberry Pi. Para testar, abra Canais e confira a seção do Guia complementar; verifique se TV Brasil/Cultura ainda reproduzem pelo KTV e se não aparecem botões que levam a sites de retransmissões desconhecidas.

## Expansão de vídeos no futuro

Para acrescentar mais **canais efetivamente reproduzíveis**, é necessário verificar a fonte original de cada canal e obter uma URL oficial autorizada, um embed publicado pela emissora para essa finalidade ou suporte ao sintonizador local. A API comunitária pode sugerir nomes para investigação, mas **não será automaticamente confiável como fonte de vídeo**.
