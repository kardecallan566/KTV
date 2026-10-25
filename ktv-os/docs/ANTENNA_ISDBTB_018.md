# KTV OS Alpha 0.18 — TV aberta brasileira por antena ISDB-Tb

## Por que é possível e o que o PC precisa

A recepção de **TV aberta terrestre por antena** é diferente da retransmissão pela Internet. O KTV OS pode receber livremente o sinal local de Globo, SBT, Record, Band, TV Cultura, TV Brasil e outras emissoras captáveis na região, independentemente de hospedarem vídeos em seus sites.

A TV Samsung normalmente já tem um sintonizador ISDB-Tb embutido, mas ele **não é automaticamente acessível pelo computador via HDMI**. Para sintonizar dentro do KTV OS é necessário um **receptor USB ISDB-Tb compatível com os drivers DVB do Linux** e uma antena conectada a esse receptor. Não basta conectar o cabo de antena à Samsung. Alguns adaptadores são de padrões DVB-T europeus e **não recebem o ISDB-Tb brasileiro**; verifique hardware, firmware e driver.

## Implementação Alpha 0.18

- O Linux detecta apenas dispositivos DVB com caminhos reconhecidos como `/dev/dvb/adapter0/frontend0` e `dvr0`, limitados aos adaptadores 0–3.
- O botão **Buscar canais da antena** inicia `w_scan -ft -c BR -X -E 0 -a 0` em processo separado: padrão terrestre Brasil, formato zap, apenas serviços gratuitos. Pode levar vários minutos; limite de 12 minutos.
- O resultado é validado, tem tamanho limitado a 256 KiB, nomes de emissoras não são aceitos como comandos e dados são salvos localmente em `~/.config/ktv-os/antenna_channels.conf`. O arquivo é privado e atualizado atomicamente. No Linux Live o estado pode desaparecer após reiniciar sem persistência configurada.
- Cada canal detectado ganha botão **▶ Assistir**. O comando `dvbv5-zap` sintoniza o serviço local e o `mpv` reproduz o `/dev/dvb/adapterN/dvr0` com o vídeo da própria antena. Nenhum site, token, scraping, login ou internet é necessário para essa rota.
- **Parar reprodução** também encerra o processo de sintonia; outra reprodução por streaming para a sintonia anterior. Uma busca não roda enquanto uma sessão DVB estiver ativa.
- A interface mostra mensagens compreensíveis se não houver receptor, nenhum canal encontrado ou problema na busca. Não faz varredura automática na inicialização, mantendo o boot rápido.
- Os canais públicos via streaming e os players oficiais integrados das versões anteriores continuam disponíveis de forma separada.

## Segurança

O navegador não escolhe frequência, caminho de dispositivo, comando externo, argumento de sintonia nem URL. Envia apenas `index` inteiro de um canal presente na lista local validada. Comandos são listas de argumentos `subprocess.Popen`, **nunca shell=True**; nenhum executável é baixado da internet. O servidor HTTP continua em `127.0.0.1` e valida origem e JSON para ações.

A busca armazena apenas canais do sinal recebido; não injeta publicidade nem remove intervalos comerciais transmitidos pela emissora. O conteúdo é reproduzido dentro do KTV. Os pacotes `w-scan` e `dvb-tools` estão nos repositórios oficiais Debian 13 e são compilados para AMD64 e ARM64.

## Como testar

1. Conecte no PC um receptor USB **ISDB-Tb compatível com Linux** e uma antena digital. Ligue o KTV OS ao televisor por HDMI.
2. Abra **Canais → TV aberta — sinal digital por antena → Buscar canais**. Aguarde até aparecer a lista.
3. Se a área de cobertura tiver SBT, Globo, Band, Record, TV Brasil ou outras emissoras livres, elas aparecerão com os nomes fornecidos pelo receptor. Clique em **Assistir**; use Q para fechar a janela mpv.
4. Caso nenhum canal seja encontrado, confira antena, sinal da região, suporte a firmware e permissões de `/dev/dvb/`. Execute `ls -l /dev/dvb/adapter0/` e `dvb-fe-tool -a 0` no console se precisar diagnosticar.
5. Sem sintonizador USB, o KTV continua com todas as funções IPTV e canais públicos previamente existentes. **Não haverá canais inventados nem botão de site externo no lugar do sinal de antena**.

### Limitações atuais

- A Alpha 0.18 não transforma a placa HDMI em capturadora. A sintonia da Samsung continua separada e não pode ser operada pelo PC sem hardware/protocolo apropriado.
- Compatibilidade real com chipsets ISDB-Tb, HD e codecs depende do driver e do adaptador; não foi testada no hardware do usuário.
- Uma ISO própria **Raspberry Pi ARM64** ainda precisa ser construída. O módulo Python e as ferramentas Debian utilizadas são multiplataforma, mas alguns adaptadores DVB/USB podem exigir firmware e alimentação adicional.
- O EPG XMLTV via internet continua independente; guia de programação transmitido por EIT/ISDB local fica para uma próxima versão.

### Fontes técnicas

- https://packages.debian.org/trixie/w-scan
- https://packages.debian.org/trixie/dvb-tools
- https://manpages.debian.org/trixie/dvb-tools/dvbv5-zap.1.en.html
- https://docs.kernel.org/userspace-api/media/dvb/frontend.html
