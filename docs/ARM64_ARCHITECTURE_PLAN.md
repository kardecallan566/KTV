# KTV — plano de arquitetura multiplataforma e ARM64

**Checkpoint:** CP01 — auditoria e documentação  
**Auditoria realizada em:** 29/10/2026  
**Branch auditada:** `main`  
**Commit de referência:** `aec1be8f0a2f9881519b2427c4601805b2469156`  
**Estado:** auditoria documental concluída; nenhuma alteração de runtime foi feita neste checkpoint.

---

## 1. Objetivo e decisões de segurança

Evoluir o KTV para compartilhar identidade visual, experiência e regras de negócio entre plataformas, sem transformar o projeto em dois produtos independentes e sem sacrificar os runtimes que já existem.

A expansão deverá preservar:

1. O KTV OS Linux atual para PCs AMD64, incluindo a ISO Live existente.
2. O protótipo Samsung Legacy/Orsay como linha separada e identificada corretamente.
3. A futura aplicação Samsung Tizen, depois de confirmar a plataforma real do televisor de referência.
4. O futuro runtime Linux ARM64 para Raspberry Pi 4 e 5.

**Regra de migração:** primeiro criar contratos e adaptadores testáveis; depois migrar um recurso por vez. Não mover, renomear ou substituir os diretórios atuais até que os testes de equivalência estejam verdes.

**Regra de distribuição:** não gerar nem anunciar uma imagem Raspberry Pi como funcional antes de validar boot, vídeo, áudio, rede, controle e reprodução em hardware real. A ISO AMD64 não deve receber kernel ou pacotes ARM.

## 2. Resumo executivo da auditoria

| Área | Situação encontrada |
|---|---|
| KTV OS para PC | Aplicação web local com backend Python; existe perfil Debian 13 Live AMD64 |
| Interface do KTV OS | HTML, CSS e JavaScript sem framework frontend |
| Backend | Python 3 e biblioteca padrão; servidor HTTP local e módulos de domínio/hardware |
| Player Linux | mpv nativo; integração direta por subprocesso e IPC Unix |
| Samsung Legacy | Widget experimental Samsung Orsay, JavaScript ES5 e APIs proprietárias antigas |
| Samsung Tizen | Não foi encontrada aplicação Tizen, manifesto Tizen ou pipeline de pacote `.wgt` |
| Código compartilhado | Não há hoje uma camada comum formal entre o widget Orsay e o KTV OS |
| Linux ARM64 | Não há runtime, pacote, instalador ou imagem ARM64 no repositório |
| Inicialização Linux | LightDM + Openbox + script supervisor; o KTV ainda não é um serviço systemd próprio |
| CI | Testes Python, verificações JavaScript e validação do construtor AMD64; sem teste físico de Pi ou Tizen |

**Conclusão:** o repositório já tem uma base útil para a expansão, mas ainda não é multiplataforma. O trabalho correto é adicionar uma arquitetura de portas/adaptadores em torno do KTV OS e criar runtimes específicos, mantendo o Orsay isolado.

## 3. Estrutura atual do repositório

### 3.1 Linhas de produto

| Diretório | Responsabilidade atual | Observação |
|---|---|---|
| `ktv-os/` | KTV OS para PC/HDMI e Debian Live | Linha principal do produto |
| `ktv-os/app/` | Interface HTML/CSS/JS do KTV OS | UI web sem framework |
| `ktv-os/linux-live/` | Perfil Debian Live, pacotes, overlay e scripts de boot | AMD64 apenas |
| `ktv-os/tests/` | Testes do backend, APIs, player, hardware e boot | Executados pela CI |
| `tv-orsay/` | Widget Samsung Legacy/Orsay | Não é uma aplicação Tizen |
| `tv-bare/`, `tv-flat/`, `tv-diagnostic/` | Widgets de diagnóstico/A-B | Experimentos separados; não são UI compartilhada |
| `installer-local/` | Servidor local, painel e empacotador de widgets Orsay | Python standard library |
| `admin-web/` | Painel web administrativo auxiliar | Não é o runtime de TV |
| `docs/` | Arquitetura, instalação, diagnóstico e roadmap | Documentação do produto |

Não foram encontrados diretórios `shared/`, `platforms/`, `apps/tizen/`, `packaging/debian/` ou equivalente, nem um projeto Tizen existente.

### 3.2 KTV OS atual

O fluxo atual é:

```text
Debian Live AMD64 ou Linux/Windows de desenvolvimento
  └── launcher.py (servidor HTTP Python em loopback)
        ├── API local /api/*
        ├── módulos de catálogo, canais, EPG e persistência
        ├── adaptadores concretos de rede, vídeo, áudio e sistema
        └── app/ (HTML + CSS + JavaScript)
              └── Chromium em tela cheia / modo kiosk

Player de vídeo:
  launcher.py -> player.py -> processo mpv -> IPC privado Unix
```

A interface conversa com o backend por rotas HTTP locais, como `/api/status`, `/api/channels`, `/api/player/play`, `/api/network/*`, `/api/hardware` e `/api/system/*`. A UI e o backend estão separados por HTTP, mas os contratos ainda não estão definidos como interfaces de plataforma versionadas.

### 3.3 Samsung Legacy/Orsay atual

O fluxo existente é:

```text
installer-local (Python)
  ├── gera widget ZIP e widgetlist.xml
  ├── serve painel/mídia/API na LAN
  └── sincronização experimental
        └── tv-orsay/
              ├── config.xml no namespace Samsung Legacy
              ├── Widget.js / sendReadyEvent()
              ├── JavaScript ES5
              └── SAMSUNG-INFOLINK-PLAYER para HLS
```

O código Orsay usa APIs como `$MANAGER_WIDGET/Common/API/Widget.js` e o objeto `SAMSUNG-INFOLINK-PLAYER`. O empacotador valida o namespace Samsung Legacy e os metadados desse widget. Isso não equivale ao runtime Tizen.

Os diretórios `tv-bare`, `tv-flat` e `tv-diagnostic` são experimentos de inicialização/diagnóstico, não uma camada compartilhada de interface.

## 4. Linguagens, frameworks e dependências

### 4.1 Código da aplicação

- **Python:** backend do KTV OS, servidor local Orsay, instalador/empacotador e ferramentas de diagnóstico.
- **JavaScript:** frontend do KTV OS em JavaScript sem framework; widget Orsay deliberadamente em ES5.
- **HTML/CSS:** interface de TV, navegador temático e páginas de administração.
- **Shell/Bash:** construtor da ISO, sessão Live, supervisor e diagnóstico.
- **Frameworks:** não foi identificado React, Vue, Angular, Qt ou outro framework de UI no runtime principal.
- **Pacotes Python externos:** não há dependências pip declaradas nos arquivos de configuração do projeto auditados; o backend usa principalmente a biblioteca padrão.

### 4.2 Dependências de sistema atuais

| Recurso | Implementação atual | Acoplamento |
|---|---|---|
| Interface | Chromium + Xorg/Openbox | Sessão gráfica Linux |
| Vídeo | mpv, subprocesso e IPC Unix | Executável mpv e recursos do sistema |
| Tela/HDMI | xrandr | X11; não é uma API universal de display |
| Áudio | pactl/PulseAudio | Servidor PulseAudio da sessão |
| Wi-Fi/Ethernet | nmcli/NetworkManager | NetworkManager |
| Controle CEC | cec-client/libCEC | Hardware CEC e ferramenta externa |
| Teclado virtual | matchbox-keyboard | X11 e pacote externo |
| USB | UDisks/udisksie e caminhos de montagem | Linux; há enumeração separada para Windows |
| TV digital | w_scan, dvb-tools e /dev/dvb | Linux DVB e sintonizador ISDB-Tb |
| Energia | systemctl poweroff + logind/polkit | Linux Live |
| Armazenamento | `~/.config/ktv-os` e backup opt-in em USB | Caminhos e montagem do host |

Os módulos já recebem alguns executores/fábricas por injeção para testes, o que ajuda a introduzir contratos sem reescrever tudo. Porém, o `launcher.py` instancia classes concretas diretamente e os módulos de hardware chamam ferramentas específicas do sistema.

### 4.3 Empacotamento e CI

- `ktv-os/linux-live/build-iso.sh` exige `uname -m == x86_64`.
- O perfil usa `--architectures amd64`, `linux-image-amd64` e bootloaders/grub específicos de PC.
- O workflow `build-ktv-os-iso.yml` gera o artefato `KTV-OS-Alpha-*-amd64`.
- O workflow de testes usa Python 3.11, unittest, Node para checagem de sintaxe JS e validação Bash do construtor.
- A CI atual não executa um boot de Raspberry Pi, não mede decodificação por hardware e não testa uma aplicação no televisor Samsung físico.

Na auditoria, a execução mais recente consultada da regressão principal estava verde: [GitHub Actions #40764108375](https://github.com/kardecallan566/KTV/actions/runs/40764108375). Isso valida os testes automatizados atuais, não o suporte ARM64/Tizen.

**Pequena inconsistência de metadados observada:** `launcher.py` declara `VERSION = 0.21.0`, mas o cabeçalho HTML ainda exibe `ALPHA 0.20` e o cabeçalho HTTP do servidor informa `KTV-OS/0.20`. Corrigir esses identificadores em um checkpoint de manutenção separado, com teste para evitar divergência futura.

## 5. Mapa de recursos e dependências de plataforma

| Recurso de produto | Lógica que pode ser compartilhada | Parte que precisa de adaptador |
|---|---|---|
| Catálogo e categorias | Modelos, filtros, favoritos e validação | Fetch/cache e armazenamento local |
| Canais pessoais | Modelo, regras e validação de URL | Persistência por plataforma |
| EPG | Parser, normalização e seleção do programa | Fonte de dados e agendamento |
| Reprodução | Estado, intenção do usuário, perfil e eventos normalizados | mpv no Linux; AVPlay no Tizen; Orsay player legado |
| Navegação | Mapa de rotas, foco e comandos semânticos | Teclas remotas, teclado, gamepad e eventos do dispositivo |
| Rede | Estado esperado e validação de entrada | NetworkManager no Linux; APIs disponíveis no Tizen |
| USB/arquivos | Regras de acesso, modelos e permissões | UDisks/mount no Linux; APIs de arquivo do Tizen |
| Imagem/áudio | Preferências e modelo de configuração | xrandr/PulseAudio ou stack ARM; APIs Tizen permitidas |
| Energia | Comando abstrato e confirmação da UI | systemd/logind no Linux; API permitida no Tizen |
| Inicialização | Estado de aplicação e recuperação | systemd/kiosk Linux; ciclo de vida Tizen |
| Identidade do dispositivo | Modelo de dados comum | `lspci`/device tree no Linux; SystemInfo/Product API no Tizen |

### 5.1 Pontos de acoplamento que devem ser removidos gradualmente

1. `launcher.py` instancia `NativePlayer`, `HardwareManager`, `NetworkManager`, `CECBridge`, `SystemActions` e outros serviços concretos.
2. `hardware.py` e `display_layout.py` pressupõem X11/xrandr e PulseAudio.
3. `input_support.py` pressupõe `/proc/bus/input/devices` e `matchbox-keyboard`.
4. `network.py` pressupõe `nmcli`.
5. `system_actions.py` pressupõe `systemctl`, logind/polkit e o sinalizador `KTV_OS_LIVE`.
6. `antenna_tv.py` pressupõe Linux DVB, dispositivos `/dev/dvb` e utilitários externos.
7. `player.py` pressupõe mpv e IPC Unix; a seleção de decodificador atual não prova que haja aceleração disponível em toda GPU.
8. `app.js` chama diretamente as rotas HTTP do KTV OS e usa DOM, Fetch, KeyboardEvent e Gamepad API.
9. `tv-orsay/js/app.js` usa eventos e objetos proprietários Orsay; não pode ser tratado como se tivesse as mesmas APIs do Chromium ou do Tizen.

## 6. Samsung: Tizen, Orsay e confirmação do modelo

Este é o principal ponto que precisa ser resolvido antes de implementar o adaptador Samsung novo.

- O repositório contém um widget **Orsay/Legacy**, e não um projeto Tizen.
- A documentação geral da Samsung lista Tizen 2.3 para a geração de TVs de 2015 e informa que `required_version=2.3` é o requisito usado para compatibilidade com modelos Samsung desde 2015. Isso é uma referência de plataforma, mas não comprova, sozinho, o runtime exato de cada variante regional/firmware.
- A página oficial de suporte do modelo UN43J5200AG confirma o modelo e disponibiliza firmware T-N14MJUABC 1080.0; ela não identifica explicitamente, no material consultado, a plataforma de execução do aplicativo.
- Portanto, **não vamos presumir que o UN43J5200AG seja Orsay ou Tizen apenas pelo nome da série, nem rebatizar o widget existente como Tizen**.

### Verificação obrigatória no aparelho

Antes do CP02 fechar a matriz de suporte, obter pelo menos uma destas evidências:

1. User-Agent do navegador da TV, verificando se contém `Tizen` e a versão da plataforma.
2. Em um app de diagnóstico Tizen autorizado, consultar `tizen.systeminfo.getCapability("http://tizen.org/feature/platform.version")` e `webapis.productinfo.getModel()`, quando essas APIs estiverem disponíveis.
3. Registrar modelo completo, versão de software e resultado de um teste com o SDK/emulador correspondente. Não publicar serial, MAC ou identificadores pessoais.

### Adaptador Tizen proposto

Se a TV for confirmada como Tizen e permitir instalação de aplicações de desenvolvedor:

- Criar um projeto web Tizen separado, com manifesto `config.xml` Tizen e pacote `.wgt`.
- Usar `TVInputDevice` para registrar teclas adicionais, mantendo as setas, Enter e Back como controles essenciais.
- Avaliar `webapis.avplay` para vídeo, buffer, estado e eventos; não presumir equivalência com mpv.
- Isolar APIs Samsung/Tizen atrás de adaptadores e verificar permissões/privileges no manifesto.
- Validar o pacote no Tizen Studio/emulador e depois no televisor real. O emulador não comprova compatibilidade de codecs, firmware ou APIs exclusivas do modelo.

O Orsay permanece no diretório e pipeline próprios até haver decisão separada sobre seu suporte físico. Não será removido nem alterado por uma migração Tizen.

## 7. Arquitetura de destino proposta

A arquitetura deve separar domínio, contratos e adaptadores. A organização abaixo é uma proposta, não uma exigência de renomear todo o repositório de uma vez:

```text
ktv-os/
  core/
    domain/          # canais, favoritos, EPG, regras e modelos
    services/        # casos de uso sem chamadas diretas ao SO
    contracts/       # portas/interfaces e eventos normalizados
  app/               # UI compartilhada gradualmente
  platforms/
    linux/
      common/        # adaptadores Linux comuns
      amd64/         # perfil atual PC/HDMI
      arm64/         # Raspberry Pi e outras placas validadas
    tizen/
      web/           # app Tizen, manifesto e integração Samsung
      adapters/      # remote, media, storage, lifecycle
  packaging/
    debian/          # pacote .deb ARM64 e scripts
    raspberry-pi/    # imagem de microSD, somente após validação
    tizen/           # build e validação .wgt
tv-orsay/            # linha Legacy/Orsay preservada
installer-local/     # ferramenta atual de sincronização Orsay
docs/
```

### 7.1 Contratos/portas a criar

As interfaces deverão usar operações semânticas, independentes de comandos do sistema:

- **MediaPlayer:** capabilities, play, pause, resume, stop, seek, status e eventos de buffer/erro/fim.
- **RemoteInput:** subscribe/unsubscribe, normalização de teclas e estado de dispositivos de entrada.
- **Display:** listar saídas, capacidades, modo atual e mudança temporária com rollback.
- **AudioOutput:** listar saídas, volume, mute e seleção quando suportados.
- **Network:** estado, scan, conexão e rádio Wi-Fi, sem expor credenciais em logs.
- **Storage:** volumes removíveis, leitura autorizada, backup e persistência.
- **SystemPower:** status, desligamento e reinício mediante confirmação explícita.
- **DeviceInfo:** arquitetura, modelo, memória, GPU, codecs e capacidades detectadas.
- **AppLifecycle:** start, stop, restart, health e logs.

Cada método deve retornar capacidades e erros estruturados. Uma funcionalidade indisponível deve ser marcada como indisponível; não deve ser simulada com dados fictícios.

### 7.2 Adaptadores por plataforma

| Plataforma | Adaptadores previstos |
|---|---|
| Linux AMD64 | Reaproveitar mpv, NetworkManager, CEC, DVB e módulos atuais; substituir gradualmente chamadas concretas por contratos |
| Linux ARM64 | mpv primeiro como candidato; detectar hwdec/codec real; integração de display/áudio/input própria do Pi; armazenamento e energia Linux |
| Samsung Tizen | Tizen Web APIs, Samsung Product APIs permitidas, TVInputDevice, AVPlay, filesystem/storage e ciclo de vida Tizen |
| Samsung Orsay | Manter o widget ES5 e player Legacy isolados; sem presumir compartilhamento de APIs proprietárias |

A lógica de domínio pode ser compartilhada mesmo quando o backend de reprodução e os eventos de controle são diferentes. O contrato deve normalizar o estado, não tentar fingir que todos os players possuem as mesmas capacidades.

## 8. Estratégia técnica para Linux ARM64

### 8.1 Base de sistema

- Referência inicial: **Raspberry Pi OS 64-bit** em Raspberry Pi 4 e Raspberry Pi 5.
- Manter Debian ARM64 como alvo de pacote quando as dependências e o boot estiverem validados.
- Não reaproveitar o script da ISO AMD64 com substituição textual de `amd64` por `arm64`.
- O boot, kernel, firmware, device tree, bootloader e configuração gráfica do Pi devem seguir a base oficial da placa.

### 8.2 Player

**Candidato inicial: mpv**, porque já é o backend Linux do KTV OS e oferece HLS, estado de reprodução e telemetria. A primeira entrega deve reutilizar o contrato do player e detectar capacidades reais.

- Testar Pi 4 e Pi 5 separadamente.
- Confirmar codec, resolução, FPS, decoder realmente ativo e frames descartados.
- Medir RAM, CPU, temperatura e estabilidade em reprodução contínua.
- Não assumir que `hwdec=auto-safe` ativa aceleração em todos os sistemas.
- Avaliar GStreamer somente se o mpv não oferecer uma integração de hardware estável para um alvo específico. Não manter dois backends apenas por precaução.
- Chromium Media APIs continuam úteis para mídia suportada pelo navegador, mas não substituem o backend nativo do KTV para todos os streams.
- FFmpeg pode permanecer como biblioteca/ferramenta do pipeline, sem criar um player paralelo.

### 8.3 Interface gráfica e boot

O perfil atual usa Xorg, Openbox, LightDM, Chromium e xrandr. A camada ARM64 deve decidir entre X11, Wayland e DRM/KMS com base em teste real da versão escolhida do Raspberry Pi OS.

O runtime de produção deverá ter:

- sessão kiosk fullscreen sem desktop visível;
- serviço systemd dedicado para o KTV, executado como usuário sem privilégios;
- `Restart=on-failure`, limites de reinício e logs no journald;
- dependência explícita de rede/display sem bloquear o boot indefinidamente;
- recuperação e modo de diagnóstico local;
- desligamento/reinício pelo logind/polkit, sem rodar a aplicação como root.

O serviço systemd próprio é uma melhoria planejada; hoje a sessão KTV é iniciada pelo autostart do Openbox e supervisionada por script.

### 8.4 Recursos e perfis

Detectar no dispositivo: modelo da placa, RAM, arquitetura, GPU/driver, conectores de vídeo, resolução, codecs/hwdec, rede, temperatura e dispositivos removíveis.

Pi 4 e Pi 5 devem ter perfis e resultados de benchmark separados. Não prometer 4K, H.264/HEVC acelerado ou super-resolução por IA sem comprovação para a combinação placa/kernel/driver/player.

## 9. Riscos técnicos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Confundir Orsay com Tizen | App não instala ou não inicia na Samsung | Confirmar runtime no televisor e manter pacotes separados |
| Regressão na ISO AMD64 | Usuário perde uma versão já testada | Manter build AMD64 e testes existentes como baseline obrigatório |
| Aceleração de vídeo diferente no Pi 4/5 | CPU alta, frames perdidos e travamentos | Matriz de codecs/driver por placa e telemetria real |
| X11/PulseAudio não equivalem ao stack do Pi | Tela, áudio ou controle não funcionam | Interfaces Display/Audio e adaptadores testados |
| CEC depende do hardware | Controle remoto não chega ao app | Teclado/gamepad como fallback; CEC opcional e detectado |
| USB/persistência muda entre distros | Perda ou corrupção de dados | Adaptador Storage, escrita atômica e testes de remoção |
| Boot/serviço com permissões excessivas | Risco de segurança e instabilidade | Usuário dedicado, privilégios mínimos, polkit/logind |
| Compartilhar código incompatível com Tizen antigo | Erros JS ou UI travada | Definir versão mínima, transpilar quando necessário e testar emulador/aparelho |
| Imagem ARM feita cedo demais | Artefato não inicializa no Pi | Primeiro pacote/instalação em SO funcional; imagem só após CP10 |
| A rede/CDN muda | Canais ficam indisponíveis | Cache limitado, erros claros, recuperação e fontes autorizadas |

### Observação sobre os anexos de boot

As três fotografias do console mostram repetição de mensagens `pcieport` / `AER: Correctable error` e erro PCIe de camada Data Link. Esse registro não identifica sozinho o componente causador e não prova defeito físico da GPU. O diagnóstico deverá correlacionar:

- `lspci -nn` e `lspci -vv` do root port e dispositivo associado;
- logs de kernel do boot, incluindo AER, DRM, nouveau/NVIDIA;
- modelo/IDs da GPU e versão do kernel;
- resultado do boot normal versus `ktv.safe=1`.

O utilitário `ktv-os-diagnostics` já coleta parte desses dados. Não adicionar `pci=noaer`, desabilitar ASPM ou alterar BIOS como correção automática sem evidência e sem um teste reversível. A investigação PCIe/GPU é uma trilha de estabilidade do runtime Linux e não deve ser confundida com a implementação ARM64.

## 10. Plano de migração por checkpoints

| CP | Entrega | Critério para avançar |
|---|---|---|
| CP01 | Auditoria e este documento | Estrutura, dependências, acoplamentos e riscos registrados |
| CP02 | Decisões de arquitetura e matriz de plataformas | Runtime Samsung confirmado; contratos e versões mínimas definidos |
| CP03 | Contratos e adaptadores iniciais | Testes de contrato passam; AMD64 e Orsay continuam intactos |
| CP04 | Runtime Linux ARM64 em SO funcional | KTV inicia em ambiente ARM64/emulado; limitações documentadas |
| CP05 | Integração gradual da UI e regras compartilhadas | Fluxos comuns funcionam sem duplicação de domínio |
| CP06 | Controle remoto e navegação | Teclado, gamepad e controle Tizen/CEC tratados por adaptadores |
| CP07 | Player ARM64 e Tizen | Reprodução e eventos normalizados; hwdec comprovado por hardware |
| CP08 | Inicialização, systemd, persistência e recuperação | Reinício automático, logs, permissões e recuperação testados |
| CP09 | Pacote Debian ARM64 e instalador | Instalar, atualizar, reverter e desinstalar sem apagar dados do usuário |
| CP10 | Matriz de testes, otimização e documentação final | Testes em Pi 4/Pi 5 e TV Samsung real; imagem só se aprovada |

### Critério de preservação em todos os checkpoints

- Testes de `tests/` (servidor/widget Orsay) continuam verdes.
- Testes de `ktv-os/tests/` continuam verdes.
- `node --check` dos arquivos JS existentes continua verde.
- O construtor AMD64 continua validando e a ISO AMD64 continua gerável.
- Nenhum pacote Orsay é substituído por pacote Tizen.
- Nenhum recurso de hardware indisponível é apresentado como funcional.

## 11. Plano de testes

### Testes automatizados

1. Testes unitários de domínio: canais, favoritos, EPG, validação e configurações.
2. Testes de contrato: MediaPlayer, RemoteInput, Display, Network, Storage, SystemPower e DeviceInfo.
3. Testes de adaptadores Linux com executores simulados, sem comandos privilegiados.
4. Testes de API e compatibilidade da UI.
5. Testes de empacotamento Debian ARM64 e verificação das dependências.
6. Testes de serviço systemd: usuário, permissões, restart, healthcheck e logs.
7. Testes de build e regressão AMD64 existentes.
8. Testes de manifesto, pacote e compatibilidade Tizen com SDK/emulador suportado.

A emulação ARM64/QEMU pode validar arquitetura de binário, instalação e partes do runtime. Ela **não** valida GPU, HDMI, áudio, Wi-Fi, CEC, temperatura ou decodificação por hardware.

### Validação física obrigatória

| Dispositivo | Testes mínimos |
|---|---|
| Raspberry Pi 4 (2/4/8 GB, conforme unidade disponível) | Boot, HDMI 1080p, áudio, Wi-Fi/Ethernet, USB, controle, codecs e reprodução contínua |
| Raspberry Pi 5 (4/8 GB, conforme unidade disponível) | Mesmos testes, mais benchmark de hwdec, temperatura e 4K apenas se suportado |
| Samsung UN43J5200AG | Confirmar plataforma/versão, instalar pacote correspondente, navegação pelo controle e reprodução autorizada |
| PC AMD64 atual | Regressão da ISO, HDMI, rede, áudio, player e modo de recuperação |

### Teste de longa duração

Para cada combinação de placa/player/codec: pelo menos 60 minutos de reprodução em 1080p, registrar FPS, frames perdidos, buffer, CPU, RAM, temperatura, estado do decoder e eventos de recuperação. O alvo de 4K só entra na matriz depois de aprovação do 1080p.

## 12. Documentação a produzir nos checkpoints

| Documento | Momento | Conteúdo |
|---|---|---|
| `docs/ARM64_ARCHITECTURE_PLAN.md` | CP01 | Auditoria, arquitetura atual/proposta, riscos, migração e testes (este documento) |
| `docs/MULTIPLATFORM_ARCHITECTURE.md` | CP02–CP03 | Contratos, eventos, versão da API e adaptadores |
| `docs/ARM64_BUILD.md` | CP04–CP09 | Ambiente de desenvolvimento, build e dependências ARM64 |
| `docs/ARM64_INSTALLATION.md` | CP09 | Instalação, atualização, rollback e remoção |
| `docs/ARM64_HARDWARE_COMPATIBILITY.md` | CP10 | Matriz comprovada de placas, codecs, displays, áudio e periféricos |

## 13. Referências consultadas

### Repositório KTV

- [README principal](../README.md)
- [Estado e roadmap consolidado](ESTADO_E_ROADMAP_DO_PROJETO.md)
- [Arquitetura do MVP Orsay](ARQUITETURA.md)
- [Diagnóstico de inicialização Linux](DIAGNOSTICO_INICIALIZACAO.md)
- [KTV OS README](../ktv-os/README.md)
- [Plano de qualidade de vídeo Raspberry Pi](../ktv-os/docs/VIDEO_QUALITY_RPI_PLAN.md)
- [Workflow de testes](../.github/workflows/ktv-tests.yml)
- [Workflow de ISO AMD64](../.github/workflows/build-ktv-os-iso.yml)

### Documentação oficial Samsung

- [Samsung Smart TV — General Specifications](https://developer.samsung.com/smarttv/develop/specifications/general-specifications.html)
- [Samsung — Retrieving Platform Information](https://developer.samsung.com/smarttv/develop/guides/fundamentals/retrieving-platform-information.html)
- [Samsung — AVPlay API](https://developer.samsung.com/smarttv/develop/api-references/samsung-product-api-references/avplay-api.html)
- [Samsung — TVInputDevice API](https://developer.samsung.com/smarttv/develop/api-references/tizen-web-device-api-references/tvinputdevice-api.html)
- [Samsung — Importing TV Applications](https://developer.samsung.com/smarttv/develop/getting-started/creating-tv-applications/importing-tv-applications.html)
- [Samsung — suporte do modelo UN43J5200AG](https://www.samsung.com/br/support/model/UN43J5200AGXZD/)

---

## Decisão final do CP01

**CP01 está concluído no nível documental.** A arquitetura recomendada é incremental: manter o KTV OS AMD64, introduzir contratos independentes do sistema, adicionar Linux ARM64 e Tizen como runtimes com adaptadores próprios e conservar Orsay como legado isolado.

**Nenhum suporte Tizen ou ARM64 está sendo declarado neste checkpoint.** O próximo bloqueio de decisão é confirmar a plataforma real da Samsung UN43J5200AG e, em seguida, fechar no CP02 os contratos e a matriz de compatibilidade.
