# Plano de IA leve — KTV OS (proposta, ainda NÃO implementada)

## Objetivo

Um assistente **local, opcional e sob demanda** para navegação, diagnóstico e suporte da interface KTV OS. Não deve controlar o sistema autonomamente sem restrições, não deve virar pré-requisito para boot e deve funcionar em computadores pequenos ou com CPU comum.

## Onde realmente ajuda

1. **Busca em linguagem natural:** "mostra documentários", "abrir meus canais favoritos" → filtro sobre dados locais autorizados.
2. **Diagnóstico assistido:** "a TV está sem som" → consulta somente estado da saída HDMI/áudio e apresenta passos; não troca de driver silenciosamente.
3. **Conectividade:** "por que estou sem internet?" → status não sensível do NetworkManager e sugestões de solução; nunca revelar ou registrar senhas.
4. **Interface acessível:** "me ajude a configurar a imagem" → abre a seção e explica 1080p, espelhamento e TV única.
5. **Recomendações locais:** sugerir canais favoritos por categoria e histórico **opcional**, sem perfis secretos nem dados enviados a terceiros.
6. **Manutenção explicável:** alertar quando USB de canais estiver desconectado, CEC ausente ou áudio HDMI não detectado.

## Arquitetura proposta em três fases

### Fase A — assistente determinístico (MVP sem modelo)

- Criar endpoint de estado **somente leitura** que consulta hardware, rede, CEC e canais. Sanitizar endereço MAC, IP local, SSIDs, URLs privados, UUIDs e credenciais de rede.
- Interpretar intenções conhecidas com regras locais (abrir telas, procurar categorias, mostrar status) e oferecer sugestões de próximos passos.
- Interface discreta "Assistente KTV", acionada por botão, teclado ou gamepad. Nada de microfone sempre ligado.
- Ações que **alteram** canais, Wi-Fi, resolução, CEC ou desligam o computador só executadas depois de um clique de confirmação no fluxo existente.
- Nenhuma execução arbitrária de shell, Python, URLs de download, instalação de software ou privilégios root.

### Fase B — modelo pequeno GGUF opcional

- Primeira candidata para teste: **Qwen3-0.6B-GGUF quantizado Q4** (licença Apache-2.0 na página oficial); avaliar alternativas **0,5–1,5 bilhões de parâmetros** por acurácia em português e hardware disponível.
- Backend: **llama.cpp** com CPU e API ligada a `127.0.0.1`, processo separado do servidor KTV OS. Limitar threads, tokens gerados, tamanho do contexto e tempo de resposta. Preferir lazy start e desligamento após inatividade.
- **Não embutir os pesos na ISO** inicial; instalação/ativação específica mediante escolha consciente, com hash SHA-256 e procedência conferidos. Linux Live efêmero precisa de espaço persistente separado para os pesos.
- Orçamento inicial a medir: **máximo de 1,5–2,5 GB adicionais de RAM durante inferência**, CPU moderada e respostas de até ~160 tokens para comandos rápidos. Estes são alvos de teste, não garantias de consumo.
- Fluxo: pergunta → classificação/intenção → resposta JSON estruturada → validação estrita no backend → proposta visível → ação confirmada. O modelo não recebe uma ferramenta de shell nem URL arbitrária.
- Fallback obrigatório: sem modelo, sem internet ou sem RAM, continuar com as regras da Fase A; vídeos sempre têm prioridade de CPU/RAM.

### Fase C — acessibilidade e preferências

- Entrada de voz **apenas por botão pressionado** e permissões explícitas; STT local separado para hardware suficientemente potente.
- Aprender preferências locais somente com opt-in e botão "Apagar minhas preferências".
- Diagnóstico com passos de recuperação e histórico resumido de incidentes, sem salvar senhas ou capturar áudio sem autorização.

## Decisões de segurança e privacidade

- O modelo é **não confiável para executar ações**; usar allowlist de ações e validação dos mesmos parâmetros usados pela UI.
- Informação de playlist/web/EPG é dado não confiável, nunca instrução para alterar o sistema.
- Toda ação destrutiva/externa exige confirmação humana independente: desligar, trocar layout HDMI, remover canais, conectar Wi-Fi, atualizar sistema, copiar para USB.
- Serviço de inferência apenas loopback, sem portas expostas à LAN e sem envio de dados para nuvem por padrão.
- Nenhum acesso a comandos root, arquivos pessoais, chaves de API, SSID/senha em prompts, metadados identificadores ou streaming de tela.
- O assistente nunca responde como fonte absoluta sobre erros de hardware; deve mostrar o estado real e limites da inferência.

## Plano de validação e decisão

1. Testar CPU x86-64 com **2 GB, 4 GB e 8 GB de RAM**, sem depender de GPU Nvidia.
2. Verificar tempo de resposta, reprodução 1080p no mpv em paralelo, memória máxima e uso de CPU.
3. Testar 30 pedidos em português brasileiro: intents simples, falas ambíguas e comandos potencialmente perigosos.
4. Testes de prompt injection em playlists, URLs e metadados de canais: nenhuma execução lateral ou privilégio extra.
5. Exigir que a versão sem IA faça boot, conecte Wi-Fi, ajuste HDMI e reproduza canais normalmente.

## Referências

- Qwen3-0.6B-GGUF: https://huggingface.co/Qwen/Qwen3-0.6B-GGUF
- llama.cpp server: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

**Decisão para o checkpoint atual:** implementar desligamento, UX/HDMI e diagnóstico; somente planejar a IA. Nenhum modelo nem downloader de pesos será incluído nesta ISO.
