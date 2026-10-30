# KTV OS — preparação de build e teste ARM64

**Checkpoint:** CP04 — launcher manual criado; validação física pendente  
**Primeiro alvo:** Raspberry Pi 4 com sistema operacional 64-bit  
**Estado:** contratos, diagnóstico e runtime manual disponíveis; ainda não existe instalador ARM64.

## 1. Objetivo

Preparar uma placa Raspberry Pi 4 com sistema de 64 bits para validar o runtime do KTV OS. Esta etapa usa uma instalação oficial e funcional do Raspberry Pi OS; não grava uma imagem KTV no microSD e não substitui o sistema operacional da placa.

## 2. Antes de começar

Registre o hardware disponível:

- modelo da placa e revisão;
- memória RAM;
- tipo/capacidade do microSD;
- fonte de alimentação;
- dissipador/ventoinha, se houver;
- monitor/TV e cabo HDMI;
- rede Ethernet ou Wi-Fi;
- teclado USB e, se disponível, controle remoto/CEC.

A quantidade de RAM e o resfriamento influenciam a escolha de resolução, navegador e teste prolongado. Não assumir que resultados de Pi 5 se aplicam ao Pi 4.

## 3. Sistema de referência

1. Use o Raspberry Pi Imager oficial para gravar uma versão 64-bit do Raspberry Pi OS.
2. Para a primeira rodada, prefira a edição Desktop para facilitar diagnóstico e abertura manual do navegador.
3. Faça o primeiro boot normalmente e confirme que o sistema operacional inicia antes de instalar ou alterar o KTV.
4. Mantenha SSH desativado se não for necessário; se habilitar, use autenticação segura e não publique senhas ou chaves.
5. Não execute scripts que particionem, formatem ou alterem o firmware.

## 4. Obter o código e executar o diagnóstico

No terminal do Raspberry Pi:

~~~bash
git clone https://github.com/kardecallan566/KTV.git
cd KTV
python3 ktv-os/platforms/linux/arm64/diagnostics.py --json --require-arm64
~~~

O comando deve identificar a arquitetura como aarch64 ou arm64. O relatório pode incluir modelo da placa, memória, temperatura disponível, dispositivos DRM, conectores de vídeo, dispositivos de entrada e presença de ferramentas como mpv/Chromium.

Para compartilhar o diagnóstico, envie o JSON removendo qualquer dado de rede ou identificador pessoal que você não queira divulgar. O script não coleta senha Wi-Fi, endereço MAC, número de série ou conteúdo de arquivos pessoais.

## 5. Executar a regressão Python no dispositivo

~~~bash
python3 -m unittest discover -s ktv-os/tests -v
~~~

A suíte testa contratos, diagnóstico e o launcher com dados simulados. Ela não prova aceleração gráfica, reprodução real ou compatibilidade de periféricos.

## 6. Iniciar o KTV manualmente

Com o Raspberry Pi OS Desktop aberto e uma sessão gráfica ativa, execute na raiz do repositório:

~~~bash
python3 ktv-os/platforms/linux/arm64/runtime.py
~~~

O launcher confirma ARM64, localiza Chromium, inicia o servidor KTV em 127.0.0.1 e abre a interface em modo kiosk. Para diagnosticar falhas de composição gráfica do Chromium, use:

~~~bash
python3 ktv-os/platforms/linux/arm64/runtime.py --safe-browser
~~~

O modo seguro desativa a composição GPU do Chromium; ele não confirma nem altera o decoder de vídeo do mpv. O padrão mantém a GPU habilitada. Encerre fechando o navegador ou pressionando Ctrl+C no terminal que iniciou o runtime.

O servidor permanece limitado a loopback. Execute o launcher a partir de uma sessão gráfica local; iniciar por SSH sem encaminhamento de display não abre a TV. A lista final de pacotes ainda será definida para o instalador, e o diagnóstico apenas verifica mpv, Chromium, systemctl e nmcli, sem instalar nada.

Ainda não há serviço systemd. Não crie uma unidade apontando diretamente para launcher.py: o launcher manual é o ponto de entrada correto enquanto desenvolvemos a supervisão e a recuperação.

## 7. O que ainda precisa ser medido na placa

- boot e login sem intervenção;
- abertura da interface KTV em tela cheia;
- navegação por setas, Enter e Back;
- áudio HDMI e saída de áudio selecionada;
- Wi-Fi e Ethernet;
- reprodução HLS 1080p e arquivos locais;
- decoder realmente ativo, FPS e frames perdidos;
- CPU, RAM e temperatura após pelo menos 60 minutos;
- recuperação após perda de rede, parada e troca de canal;
- desligamento seguro.

## 8. Critério para gerar instalador ou imagem

O instalador Debian ARM64 só será iniciado após o runtime manual estar estável. A imagem de microSD só será criada depois de testar instalação, atualização, recuperação e boot em uma placa física. A ISO AMD64 existente continua sendo exclusiva para PCs x86_64.
