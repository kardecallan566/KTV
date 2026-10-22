# KTV OS — Alpha 0.1

Interface de TV para computador conectado a uma televisão por HDMI. Esta pasta **não é ainda uma distribuição Linux, nem um firmware Samsung**. É um *shell* de TV rodando no navegador do computador. Isolado do KTV Orsay em ../tv-orsay/.

## Teste imediato no Windows (PC -> HDMI -> Samsung)

1. Conecte o computador à Samsung por cabo HDMI.
2. No controle da TV, pressione SOURCE e selecione a entrada HDMI do computador.
3. No Windows, pressione Win+P e selecione "Somente segunda tela" ou "Duplicar" conforme sua preferência. Ajuste para 1920x1080 / 60 Hz se disponível.
4. No terminal, a partir da raiz do repositório:
   \`\`\`powershell
   git pull origin main
   cd ktv-os
   python launcher.py --open
   \`\`\`
   Também é possível dar duplo clique em \`ktv-os/iniciar_windows.bat\`.
5. No navegador, pressione F11 para tela cheia. Use setas, Enter e Esc para navegar. Também há botão interno de tela cheia (F).

O servidor fica acessível **somente em http://127.0.0.1:8787/**, no próprio PC. O Windows precisa de Python 3; nenhuma dependência Python adicional.

## Reproduzir arquivos de um pendrive ligado ao computador

Insira o pendrive **no computador** e veja a letra da unidade, por exemplo E:. Inicie:

\`\`\`powershell
python launcher.py --open --media-dir "E:\"
\`\`\`

Por segurança, o KTV OS **só lê arquivos na pasta escolhida**. Na alpha, são suportados arquivos diretamente nessa pasta (não faz varredura recursiva) nos formatos MP4, WebM, MP3, M4A, PNG, JPG/JPEG e GIF. A reprodução depende dos codecs do navegador. O servidor oferece HTTP Range para vídeos.

O recurso **USB da Samsung** não é acessível por um sistema externo conectado por HDMI. Detecção de unidades USB no Windows é apenas informativa: para conceder acesso a mídias, escolha a pasta em \`--media-dir\`.

## Canais personalizados

Na primeira execução, será criado \`~/.config/ktv-os/channels.json\`:

\`\`\`json
{
  "channels": [
    {"name": "Meu canal", "url": "https://meu-servidor.exemplo/live.m3u8", "category": "Pessoal"}
  ]
}
\`\`\`

Edite esse arquivo e entre em "Canais" novamente. Somente URLs HTTP/HTTPS diretas com extensão \`.m3u8\` ou \`.mp4\` são aceitas, e não há links comerciais pré-configurados.

**Limite do MVP:** a lista exibe streams HLS, mas navegadores desktop geralmente não tocam \`.m3u8\` diretamente. A integração com um player nativo ou HLS.js é checkpoint posterior; não confunda cadastro com reprodução.

## TV aberta, HDMI e controle remoto

- **TV aberta:** pressione SOURCE no controle Samsung e selecione TV/Antena. Um eventual sintonizador ISDB-Tb USB no PC exigirá driver e software dedicado.
- **Outras entradas HDMI:** pressione SOURCE na própria TV. O KTV OS externo **não consegue ler outras entradas HDMI da Samsung**; HDMI-CEC e infravermelho são possibilidades a investigar.
- **Controle remoto:** teclado do PC e controles que enviem teclas funcionam no shell. HDMI-CEC do controle Samsung depende de hardware e compatibilidade, não foi implementado ainda.

## Pode rodar diretamente de um pendrive?

**No computador, sim. Na porta USB da Samsung, não.** Para testar sem mexer no Windows, inicialize uma distribuição Linux **Live USB** no PC (opção "Try Ubuntu", sem instalar) e execute o KTV OS nela. A documentação oficial da Canonical explica o procedimento:

https://ubuntu.com/desktop/docs/en/latest/tutorial/try-ubuntu-desktop/

Criar esse pendrive **apaga os arquivos nele**. Faça backup e confira qual unidade está selecionada. Não tente atualizar o firmware da Samsung com a ISO/Linux. Esta alpha não inclui uma imagem bootável própria: o pendrive de Ubuntu é a base experimental; o KTV OS precisa estar acessível nessa sessão, por exemplo em outra mídia, uma cópia local ou clonando o GitHub. Sessões Live sem persistência perdem mudanças ao reiniciar.

### Atenção ao ASUS TUF A15

O notebook com RTX 3050 pode exigir drivers NVIDIA para desempenho e saída HDMI ideais no Linux. O modo Live pode usar drivers abertos e ter limitações. Primeiro teste a imagem na TV; não altere a instalação Windows ou a BIOS sem necessidade.

## Estrutura

- \`app/\`: interface TV 1080p responsiva, navegação teclado.
- \`launcher.py\`: servidor HTTP local, catálogo de canais, biblioteca opcional e estado.
- \`iniciar_windows.bat\` / \`iniciar_linux.sh\`: inicialização em sistema já instalado.
- \`tests/\`: testes automatizados sem dependências externas.

**Segurança:** servidor apenas em loopback; evite abrir porta 8787 para a rede. O diretório \`.ktv-os/\` não entra no Git.

Próximos passos: player Kodi/mpv para HLS e canais, seleção de diretório USB na interface, controle remoto/CEC, hardware para ISDB-Tb, instalação em USB Linux com persistência, depois distribuição Linux KTV dedicada.


## KTV OS Alpha 0.2 — Linux inicializável pelo computador

**Agora existe um perfil de construção de um sistema Linux Live real**, diferente da Alpha 0.1 que roda no navegador do Windows. O Linux Live contém kernel, módulos de hardware, NetworkManager, áudio, LightDM e Openbox, faz login automaticamente na sessão Live e abre a interface KTV OS em tela cheia no Chromium. O Windows não é executado neste processo.

O código e os passos de build estão em [linux-live/README.md](linux-live/README.md). A imagem é criada com `live-build` sobre Debian 13, gerando uma ISO híbrida para pendrive ligado ao **computador**. Os arquivos de configuração ficam em `~/.config/ktv-os/channels.json` (no Live, temporário, sem persistência neste checkpoint).

**Atenção:** não coloque a ISO na porta USB da Samsung, não use o menu Atualização de Software da TV e não substitua o firmware original. O HD/SSD do computador não será formatado ao executar o Linux Live, mas a gravação da imagem no **pendrive selecionado** apagará os dados dele. Hardware NVIDIA e compatibilidade UEFI precisam ser testados fisicamente.


## KTV OS Alpha 0.3 — reprodução nativa e USB

O SO agora inclui o **mpv** no Linux Live e abre HLS `.m3u8` e MP4 autorizados em janela nativa de tela cheia. Na lista de Canais, selecione o cartão e pressione Enter. O mpv aparece à frente da interface; pressione **Q** na janela do mpv para sair e voltar ao KTV OS. Na interface também existe um botão para interromper reprodução. O backend não aceita URLs arbitrárias enviadas ao player: só índices de canais previamente cadastrados e arquivos autorizados.

No computador Windows, é possível testar instalando `mpv` no PATH; se não estiver instalado, o sistema mostra uma mensagem e mantém o fallback HTML5 para arquivos locais.

A seção USB mostra pendrives montados **no computador**, permitindo abrir os arquivos da raiz, reproduzir vídeos/áudios e visualizar fotos. No Linux Live, `udiskie` cuida da montagem automática via UDisks2. Em Windows, as unidades removíveis aparecem por letra. Não são acessadas unidades ligadas à porta USB da Samsung. Acesso é apenas leitura pela interface.

Ainda não há varredura recursiva de subpastas, playlists M3U completas, controle HDMI-CEC nem sintonizador ISDB-Tb. As alterações em canais feitas no Live sem persistência serão perdidas ao reiniciar.


## Alpha 0.4 — gerenciar canais pela TV

Abra **Canais → Adicionar canal** e preencha nome, URL autorizada `.m3u8`/`.mp4` e categoria. A lista permite assistir, favoritar, editar, mover para cima/baixo e excluir (com confirmação). Use teclado para inserir URLs; a navegação por controle/teclas continua nos botões. As alterações são salvas automaticamente em `~/.config/ktv-os/channels.json`, usando gravação atômica.

Para preservar dados ao reiniciar o Linux Live, conecte um **segundo pendrive de dados** ao computador e abra **Configurações → Backup de canais em pendrive**. Selecione-o, clique em **Salvar backup** e, em outra sessão, **Restaurar backup**. A restauração exige confirmação e substitui a lista atual. O arquivo fica na raiz do pendrive como `KTVOS-channels-backup.json`. Nenhuma unidade é formatada. **Ainda não é persistência automática** no USB do próprio boot; essa função será um checkpoint separado.
