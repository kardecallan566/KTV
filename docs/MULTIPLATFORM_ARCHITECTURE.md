# Arquitetura multiplataforma do KTV OS

**Checkpoint:** CP02 concluído para a trilha Linux ARM64; CP03 iniciado  
**Contrato inicial:** 1.0  
**Alvo prioritário:** Raspberry Pi 4 (64-bit)  
**Estado:** contratos, diagnóstico e primeiro adaptador mpv criados; runtime ARM64 ainda não integrado ao launcher.

## 1. Decisões desta etapa

1. O Raspberry Pi 4 passa a ser o primeiro alvo físico da expansão.
2. Raspberry Pi OS 64-bit será a base de referência inicial. O KTV não substituirá o bootloader, firmware ou kernel da placa.
3. O player nativo mpv permanece como backend primário candidato para Linux ARM64, por já ser usado no KTV OS atual. A aceleração de vídeo precisa ser comprovada durante a reprodução no Pi.
4. A interface HTML/CSS/JavaScript atual será preservada e integrada ao runtime ARM64 gradualmente.
5. O serviço HTTP do KTV continuará limitado a loopback por padrão; não abrir a API de controle para a rede local ou internet sem autenticação e revisão específica.
6. O runtime AMD64 e o construtor da ISO atual continuam separados e são a linha de regressão.
7. O widget Samsung Legacy/Orsay não será renomeado nem alterado como se fosse Tizen.
8. A plataforma exata da Samsung UN43J5200AG continua pendente de confirmação no próprio aparelho. Essa pendência não bloqueia o trabalho no Raspberry Pi.

## 2. Matriz de plataformas

| Plataforma | Prioridade | Interface | Player | Estado |
|---|---:|---|---|---|
| Linux AMD64 / PC HDMI | Baseline | UI atual + Chromium | mpv | Implementado; preservar |
| Linux ARM64 / Raspberry Pi 4 | 1 | UI atual + Chromium | mpv candidato | Fundação em andamento |
| Linux ARM64 / Raspberry Pi 5 | 2 | UI atual + Chromium | mpv candidato | Planejado; validar separadamente |
| Samsung Legacy / Orsay | Manutenção isolada | Widget ES5 existente | Player nativo legado | Experimental; preservar |
| Samsung Tizen | Após identificar TV | Web app Tizen própria | AVPlay a avaliar | Não implementado |

## 3. Camadas e limites

~~~text
Interface KTV (HTML/CSS/JS)
        |
        | HTTP local /api/*
        v
Serviços de aplicação e domínio
        |
        v
Contratos independentes de plataforma
        |
        +---- Linux AMD64 adapters (atuais, migração gradual)
        |
        +---- Linux ARM64 adapters (Raspberry Pi)
        |
        +---- Tizen adapters (futuro, APIs oficiais)

tv-orsay/ permanece isolado e não implementa esses contratos.
~~~

### 3.1 Domínio compartilhável

Catálogo, favoritos, canais pessoais, EPG, validação de fontes, estado de reprodução e regras de navegação devem permanecer independentes de comandos do sistema. A migração não deve copiar regras de negócio para cada adaptador.

### 3.2 Adaptadores de plataforma

Um adaptador converte uma operação semântica em API local ou API do dispositivo. Exemplo: o contrato de reprodução expõe play/pause/status; o adaptador Linux usa mpv; um futuro adaptador Tizen poderá usar AVPlay. O contrato não promete que todas as plataformas suportem os mesmos codecs, eventos ou opções.

## 4. Contratos v1.0

O módulo inicial está em ktv-os/core/contracts.py. Os modelos e Protocols são Python padrão e não adicionam dependências externas. O primeiro adaptador mpv está em ktv-os/platforms/linux/arm64/mpv_adapter.py; ele normaliza o estado do player existente e envia somente comandos fixos pelo socket IPC privado.

| Contrato | Responsabilidade |
|---|---|
| MediaPlayer | Reprodução, pausa, retomada, busca, parada, estado e capacidades |
| RemoteInput | Eventos semânticos de teclas e controle remoto |
| DeviceInfoProvider | Identidade e capacidades detectadas do dispositivo |
| DisplayAdapter | Saídas, modos, mudança temporária e rollback |
| AudioOutputAdapter | Saídas, volume e mute |
| NetworkAdapter | Estado, busca e conexão Wi-Fi |
| StorageAdapter | Volumes e backup por identificadores autorizados |
| SystemPowerAdapter | Desligamento/reinício com confirmação na camada de aplicação |
| AppLifecycleAdapter | Healthcheck e reinício supervisionado |

Os tipos centrais são:

- Capability: informa se uma função existe, a fonte da informação e o motivo quando indisponível.
- OperationResult: resultado estável com ok, code, message e dados opcionais.
- MediaStatus: estado de reprodução e telemetria normalizada; valores desconhecidos permanecem None.
- RemoteKeyEvent: tecla, ação, origem e repetição.
- DeviceInfo: plataforma, arquitetura, modelo, memória, temperatura, GPU e conectores.

### 4.1 Regras de compatibilidade

- Mudanças aditivas podem permanecer na versão minor do contrato.
- Remoção ou alteração incompatível de campo/método exige nova versão major.
- Adaptadores devem declarar capacidades reais; ausência de hardware resulta em available=false.
- Não preencher codec, FPS, decoder, temperatura ou estado com valores presumidos.
- Mensagens e códigos de erro não podem conter senhas Wi-Fi, tokens, URLs assinadas ou dados pessoais.
- Operações de energia, conexão de rede e gravação em armazenamento exigem autorização explícita na camada de aplicação.
- Os contratos não executam comandos nem concedem privilégios.

### 4.2 Erros normalizados

Códigos iniciais recomendados: unsupported, not_available, invalid_argument, permission_denied, device_busy, timeout, network_error, player_error e internal_error. O texto pode ser localizado; o código é estável para a UI e testes.

## 5. Trilha Raspberry Pi 4

A primeira instalação de desenvolvimento será feita sobre Raspberry Pi OS 64-bit já inicializado. Não será usada a ISO AMD64 e ainda não será gerada imagem própria de microSD.

Ordem de integração:

1. Diagnosticar arquitetura, modelo, RAM, temperatura, DRM/HDMI, dispositivos de entrada e dependências.
2. Iniciar o servidor KTV e abrir a UI atual no Chromium em modo janela/kiosk.
3. Testar navegação por teclado USB e controle remoto compatível com o hardware disponível.
4. Conectar o adaptador mpv ao runtime e medir o decoder realmente ativo durante HLS/arquivo de teste. O adaptador já existe, mas ainda não foi conectado ao launcher.
5. Adaptar rede, áudio, display e energia conforme APIs detectadas no Raspberry Pi OS.
6. Criar serviço systemd com usuário sem privilégios, recuperação e logs.
7. Empacotar e documentar instalação/atualização antes de considerar uma imagem microSD.

O diagnóstico inicial está em ktv-os/platforms/linux/arm64/diagnostics.py. Ele é somente leitura e não altera boot, pacotes, firmware ou permissões.

### 5.1 Aceleração de vídeo

A presença de /dev/dri, de uma GPU ou da opção hwdec=auto-safe não comprova que o decoder de hardware está ativo. O teste deverá registrar:

- codec e resolução da fonte;
- FPS observado e frames perdidos;
- propriedade hwdec-current retornada pelo mpv;
- uso de CPU/RAM e temperatura;
- duração e estabilidade da reprodução.

O status not_verified é intencional até haver evidência de uma sessão real.

## 6. Preservação do runtime atual

Nenhuma migração desta etapa altera launcher.py, player.py, hardware.py, network.py, system_actions.py, o app web atual ou a ISO AMD64. Os contratos foram adicionados em paralelo para que o código existente possa ser migrado um serviço por vez.

Critérios permanentes de regressão:

- python -m unittest discover -s tests -v
- python -m unittest discover -s ktv-os/tests -v
- node --check dos arquivos JavaScript atuais
- bash -n e build-iso.sh --check do construtor AMD64

## 7. Próximos checkpoints

| CP | Próxima entrega | Critério |
|---|---|---|
| CP03 | Contratos testados e primeiro adaptador Linux ARM64 | Testes simulados passam sem alterar o runtime AMD64 |
| CP04 | Inicialização do KTV em Raspberry Pi OS 64-bit | Servidor e UI abrem em ambiente ARM64 real |
| CP05 | Integração gradual da UI e navegação | Fluxos principais funcionam com teclado/controle |
| CP06 | Adaptadores de input, display, áudio e rede | Capacidades detectadas e erros claros |
| CP07 | Reprodução mpv no Pi 4 | 1080p validado com telemetria e teste prolongado |
| CP08 | Serviço systemd, persistência e recuperação | Boot automático, logs e permissões mínimas |
| CP09 | Pacote/instalador ARM64 | Instalação, atualização e rollback seguros |
| CP10 | Matriz física e imagem microSD | Boot, vídeo, áudio, rede, controle e estabilidade aprovados |

## 8. Estado honesto da implementação

**Implementado neste checkpoint:** contratos Python v1.0, modelos normalizados, diagnóstico ARM64 somente leitura, primeiro adaptador mpv para o contrato e testes automatizados simulados.

**Ainda não implementado:** integração do adaptador mpv ao launcher, servidor/UI integrado no Raspberry Pi, serviço systemd, pacote .deb, instalador, imagem microSD e aceleração comprovada.

A placa física continua necessária para confirmar HDMI, áudio, Wi-Fi, controle, codecs, temperatura e estabilidade.
