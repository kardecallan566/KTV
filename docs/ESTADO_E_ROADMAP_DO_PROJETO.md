# KTV — estado atual do projeto e roadmap consolidado

**Atualizado em:** 28/10/2026  
**Versão mais recente do KTV OS verificada:** Alpha 0.21 (aplicação 0.21.0)  
**Branch principal:** main  
**Commit funcional de referência anterior à Alpha 0.21:** 8ddd591c6eca1d008e63b6dcbe76cc9aafaa518a

Este documento reúne o que existe no repositório, o que já foi implementado, o que é experimental, o que ainda precisa ser validado em equipamento físico e os próximos passos planejados. Ele é um resumo de estado, não uma promessa de que todas as fontes de vídeo funcionarão continuamente.

## 1. Resumo executivo

O repositório contém **dois projetos relacionados, mas diferentes**:

1. **KTV OS** — a linha ativa: interface de TV executada em um computador conectado à Samsung por HDMI. Tem uma imagem Debian Live AMD64, player nativo, catálogo de canais, navegador temático, rede, biblioteca local, ajustes de HDMI/áudio e integração opcional com sintonizador USB.
2. **KTV Legacy / Samsung Orsay** — protótipo separado para testar um widget e um servidor local para Smart TVs Samsung antigas. Não é o mesmo sistema que KTV OS e não altera o firmware da TV.

| Área | Estado atual |
| --- | --- |
| KTV OS Alpha 0.21 | Fallback automático de decodificação compatível implementado; validação física pendente |
| Testes automatizados | Aprovados para a Alpha 0.21 no [workflow de regressão](https://github.com/kardecallan566/KTV/actions/runs/40762109653) |
| ISO Linux Live AMD64 | Build da Alpha 0.21 concluído; artefato `KTV-OS-Alpha-0.21-amd64` disponível no workflow |
| Reprodução de canais | Implementada; a disponibilidade varia por fonte, rede, codec e autorização |
| Pluto TV | Catálogo dinâmico, favoritos e mecanismo de recuperação automática implementados; teste físico prolongado ainda necessário |
| Rei dos Canais | Integração somente de metadados/guia; não adiciona 104 transmissões |
| Raspberry Pi ARM64 | Ainda não existe imagem própria validada |
| Assistente de IA e melhoria de imagem por IA | Planejados, não implementados |
| Canais pagos | Sem integração de assinatura/licença; apenas estudar integração oficial autorizada |
| Samsung Orsay | Protótipo separado; abertura e reprodução completas no Smart Hub ainda precisam de confirmação conclusiva |
| Nova fase multiplataforma | CP01 concluído; CP02 definiu Raspberry Pi 4 como primeiro alvo; CP03 criou contratos, diagnóstico e primeiro adaptador mpv; runtime ainda não integrado |

**Importante sobre validação:** a ISO e os testes automatizados confirmam que o código compila e passa pela suíte do projeto. Isso não substitui testes de boot, imagem/áudio, Wi-Fi, canais e estabilidade na TV física. O usuário confirmou bons resultados com a Alpha 0.11; os recursos acrescentados nas Alpha 0.12–0.21 precisam de uma rodada de validação física correspondente.

## 1.1 Nova fase multiplataforma (CP01)

A auditoria CP01 foi concluída e a arquitetura CP02 definiu o Raspberry Pi 4 com Raspberry Pi OS 64-bit como primeiro alvo físico. O CP03 criou contratos Python v1.0, diagnóstico ARM64 somente leitura e o primeiro adaptador mpv com testes simulados. Consulte [plano de auditoria](ARM64_ARCHITECTURE_PLAN.md), [arquitetura multiplataforma](MULTIPLATFORM_ARCHITECTURE.md) e [preparação de build/teste ARM64](ARM64_BUILD.md). **O adaptador ainda não está conectado ao launcher; não existe instalador, pacote ou imagem microSD validada.**

O KTV OS AMD64 e o protótipo Samsung Legacy/Orsay continuam preservados. A plataforma efetiva da Samsung UN43J5200AG permanece pendente de confirmação no próprio aparelho; essa verificação não bloqueia a trilha Raspberry Pi.

## 2. Arquitetura atual do KTV OS

- **Sistema:** Debian 13 Live, arquitetura AMD64 (PC Intel/AMD), com sessão gráfica, login automático e interface em modo quiosque.
- **Interface:** aplicação web local em tela cheia, com visual de central de TV.
- **Servidor:** Python, ouvindo em loopback (127.0.0.1:8787 no modo de desenvolvimento), para que a interface local controle os recursos permitidos.
- **Player:** mpv nativo para streams e arquivos compatíveis; algumas emissoras também oferecem players oficiais incorporados.
- **Boot:** sessão Linux Live iniciada a partir de pendrive conectado ao computador. O pendrive de boot não é o USB da Samsung, e o KTV OS não substitui o firmware da TV.
- **Construção:** script de live-build e workflow GitHub Actions para gerar a ISO.
- **Persistência:** opcional e limitada a dados de canais/favoritos; não equivale a uma instalação persistente completa do Linux.

## 3. O que já está implementado

### 3.1 Sistema, inicialização e recuperação

- Imagem Debian Live AMD64 e inicialização direta no KTV OS.
- LightDM/Openbox e Chromium em modo quiosque.
- Modo de recuperação gráfica para máquinas com falhas de GPU/PCIe: parâmetro opcional de boot `ktv.safe=1`, renderização sem aceleração e diagnóstico local.
- Fallback após encerramentos rápidos do Chromium para evitar reinicialização infinita.
- Coleta local de diagnósticos da sessão gráfica, LightDM, PCIe/AER e DRM. Os relatórios não são enviados automaticamente.
- Ação de desligar o computador com confirmação e verificações de segurança. Ela não desliga automaticamente a televisão Samsung.
- Testes automatizados para a estrutura de boot, empacotamento e módulos de sistema.

### 3.2 Interface, navegação e teclado

- Interface otimizada para uso como central de TV, com seções de Canais, navegador, rede, mídias, entradas, imagem/som e configurações.
- Navegação por teclado e mouse; suporte de entrada é detectado quando possível.
- Teclado virtual com botão para abrir/fechar e possibilidade de mover sua janela na tela.
- Navegador personalizado com tema verde, pesquisa e controles de abertura.
- O navegador continua sujeito às políticas dos sites externos, a anúncios e a bloqueios de reprodução; o tema do KTV não remove nem altera conteúdo de terceiros.
- A cobertura completa de caracteres, interação com mouse/teclado e usabilidade no Raspberry Pi precisam ser verificadas no hardware alvo.

### 3.3 Canais e catálogos

- Cadastro, edição e remoção de canais pessoais pela interface, com validação dos dados.
- Importação de playlists M3U, sujeita a limites e validação de fontes.
- Catálogo comunitário baseado em fontes pré-configuradas e hosts permitidos; os dados são externos e podem mudar ou ficar indisponíveis.
- Catálogo de canais públicos institucionais, com endereços restritos por lista permitida.
- Verificação preliminar de streams antes de iniciar reprodução. Uma verificação bem-sucedida é um diagnóstico pontual, não garantia de disponibilidade futura.
- Busca e filtros de catálogo por categoria quando os metadados da fonte estão disponíveis.
- Guia XMLTV/EPG no backend, com consulta de programação atual/próxima para as fontes compatíveis. A cobertura depende da qualidade e atualização de cada guia.
- A tela de TV aberta separa transmissão por internet, sinal recebido por antena e informação de programação.

### 3.4 Pluto TV

- Catálogo dinâmico de canais ao vivo obtido de uma fonte comunitária; não depende de uma lista fixa incorporada ao aplicativo.
- Pesquisa/categorias e paginação do catálogo.
- Favoritos armazenados como IDs de canal, não como URLs assinadas ou tokens temporários.
- Renovação do link do canal quando o supervisor tenta recuperar uma sessão interrompida.
- Supervisor de reprodução para Pluto: verifica o estado do mpv, tenta recuperar encerramentos inesperados e travamentos prolongados quando a telemetria permite, usa intervalos progressivos e limita as tentativas.
- Pausar, fechar com Q ou pressionar Parar deve ser respeitado: o sistema cancela a recuperação quando o usuário encerra ou troca de fonte.
- O status da recuperação é mostrado na interface sem devolver JWTs ou links assinados.

**Limite:** o mecanismo melhora a recuperação, mas não pode garantir reprodução infinita se a fonte comunitária/CDN cair, a URL não puder ser renovada, a rede falhar, o serviço restringir o acesso ou o stream mudar. O tempo de reprodução prolongada precisa ser validado fisicamente.

### 3.5 Reprodução e qualidade

- Reprodução nativa pelo mpv para formatos de stream e arquivos que o player/codec suporte, incluindo HLS e formatos diretos compatíveis.
- Perfis de qualidade: Econômico, Equilibrado e Melhor disponível.
- Telemetria de resolução, codec, FPS e estado de vídeo quando o mpv fornece esses dados.
- Modo de decodificação compatível como tentativa manual de recuperação para áudio sem imagem ou incompatibilidade de codec.
- Fallback automático de uma única tentativa para canais dos catálogos público, Pluto e comunitário quando a telemetria confirma áudio sem saída de vídeo por vários ciclos (aproximadamente 12–15 segundos). Não é aplicado a canais pessoais/mídia local nem durante pausa; a decodificação por software pode usar mais CPU.
- Janela/player integrado ao fluxo da interface, com ação de parar e voltar ao KTV OS.
- Players incorporados somente para destinos oficiais previamente permitidos, atualmente com exemplos da TV Brasil/EBC e TV Cultura.
- O KTV não elimina anúncios do vídeo original, não extrai chaves e não contorna DRM, autenticação, restrições geográficas ou proteções do provedor.
- Melhorias determinísticas de seleção de fonte/decodificação são diferentes de super-resolução por IA: esta última ainda não foi implementada.

### 3.6 TV aberta e antena

- Catálogo de transmissões públicas por internet para alguns canais institucionais, condicionado à disponibilidade real das fontes.
- Integração opcional com receptor USB **ISDB-Tb** compatível com Linux e antena conectada ao receptor.
- Busca local de canais com ferramentas DVB, validação dos resultados e reprodução do sinal recebido no mpv.
- A sintonia pela antena funciona sem scraping de sites ou tokens de internet.
- O sintonizador embutido na Samsung não fica automaticamente disponível ao PC por HDMI. Para receber os canais dentro do KTV OS, é necessário um receptor USB compatível.
- O KTV OS não transforma uma saída HDMI do PC em entrada HDMI capturável e não controla todas as fontes internas da Samsung.

### 3.7 Guia do Rei dos Canais (Alpha 0.20)

- Existe um conector de leitura da API anunciada pelo Rei dos Canais para consultar metadados de programação de um conjunto restrito de emissoras abertas.
- A integração usa cache, limites de tamanho, HTTPS fixo e uma lista permitida de nomes.
- A interface mostra programação atual/próxima quando os dados são válidos.
- **Não importa nem executa** embeds, HTML, scripts, anúncios, cookies, tokens ou URLs de vídeo dessa fonte.
- Para assistir, utiliza uma fonte já validada pelo KTV ou um canal recebido pelo sintonizador local.

**Estado real:** o acesso externo à API não pôde ser confirmado na verificação que originou a Alpha 0.20. Testes usam respostas simuladas para validar o parser e as proteções. A integração não significa que o site forneça 104 canais funcionais nem que tenha direitos de retransmissão sobre os canais listados.

### 3.8 Rede, HDMI, som e hardware

- Estado de interfaces Ethernet/Wi-Fi via NetworkManager.
- Pesquisa de redes Wi-Fi e conexão mediante ação explícita do usuário.
- Diagnóstico de hardware e dispositivos locais.
- Detecção de saídas de vídeo, seleção de modo/resolução e opção de espelhar o notebook ou usar somente a TV HDMI.
- Alterações de layout são temporárias e usam confirmação/rollback quando suportado.
- Seleção de saída de áudio e controles de volume/mudo conforme os dispositivos disponíveis.
- Integração experimental HDMI-CEC para comandos limitados, quando existe adaptador/hardware compatível.
- As funções de CEC dependem do hardware: uma porta HDMI comum nem sempre transmite comandos CEC, e o KTV OS não promete controle total da TV.

### 3.9 Arquivos locais, USB e persistência

- Biblioteca de arquivos locais apontando para uma pasta escolhida pelo usuário.
- Acesso restrito à pasta configurada, com lista de formatos permitidos e suporte a solicitações HTTP Range para vídeo.
- Detecção de unidades removíveis conectadas ao computador; o USB ligado diretamente à Samsung não fica visível ao KTV OS via HDMI.
- Backup/restauração de canais por arquivo em um pendrive escolhido explicitamente.
- Persistência opcional em um dispositivo de dados, com marcador próprio e sincronização de canais/favoritos Pluto.
- Não formata automaticamente unidades, não modifica o firmware e não grava dados na unidade de boot sem autorização.
- Em uma sessão Live sem persistência completa, dados fora do escopo de backup podem desaparecer ao reiniciar. Em particular, perfis/senhas Wi-Fi não são garantidos entre reinicializações.

### 3.10 Segurança implementada

- Servidor de desenvolvimento limitado a loopback, sem recomendação de expor a interface de controle à internet.
- Validação de IDs, URLs, categorias, JSON e caminhos de mídia.
- Listas permitidas para fontes de canais, players incorporados e protocolos.
- Limites de tamanho, timeouts, cache e ausência de redirects para alguns leitores de fontes externas.
- Comandos de sistema usam argumentos validados e não aceitam comandos arbitrários vindos da página.
- Ações sensíveis como desligar, conectar Wi-Fi, mudar layout ou restaurar backup exigem interação explícita.
- Links temporários e tokens de sessão não devem ser persistidos em favoritos ou exibidos na telemetria.
- Conteúdo de páginas, playlists e EPG é dado não confiável, nunca uma instrução para executar comandos.

Essas proteções reduzem riscos, mas não equivalem a uma auditoria formal nem tornam seguros todos os sites ou streams externos.

## 4. KTV Legacy / Samsung Orsay — estado separado

O repositório também contém um protótipo voltado a Smart TVs Samsung antigas:

- Servidor local Python e painel administrativo com token.
- Preview no navegador, estado/playlist e endpoints de diagnóstico.
- Gerador de pacotes/widgetlist para o ambiente Orsay e testes de sincronização em LAN.
- Experimentos com reprodução HLS pelo plugin nativo Samsung.
- Documentação específica de instalação e diagnóstico.

**Não confundir com KTV OS:** o protótipo Orsay não é uma distribuição Linux para a TV, não substitui o firmware e não compartilha a arquitetura do player mpv do KTV OS.

**Pendência importante:** a documentação de referência registra que a abertura completa dos widgets e a reprodução dentro do ambiente Smart Hub não foram confirmadas de forma conclusiva no modelo físico alvo. A exibição de uma página no WebBrowser da TV não prova que o widget instalado funciona. Antes de investir em novos recursos Orsay, é necessário fechar esse teste de compatibilidade ou manter essa linha explicitamente experimental.

## 5. Limitações conhecidas e o que ainda não está pronto

- [ ] Imagem bootável própria para Raspberry Pi ARM64; a ISO atual é AMD64 e não deve ser usada como se fosse imagem Pi.
- [ ] Matriz física de compatibilidade para Raspberry Pi 4/5, RAM, codecs, aceleração gráfica, Wi-Fi, áudio, HDMI e temperatura.
- [ ] Teste de longa duração da Pluto TV em Alpha 0.21 e confirmação de recuperação após perda de rede/URL e de fallback automático em streams sem vídeo.
- [ ] Verificação real da disponibilidade da API externa do Rei dos Canais e consistência do EPG; o conector deve falhar sem quebrar os demais canais.
- [ ] Mais fontes de vídeo gratuitas/oficiais e autorizadas, com proveniência documentada, diagnóstico e teste periódico.
- [ ] Melhorar a distinção entre stream indisponível, áudio sem vídeo, vídeo congelado, fim de playlist, DRM e falha de rede, sem prometer diagnósticos impossíveis.
- [ ] Revisar a experiência do navegador verde, teclado virtual, símbolos, mouse e navegação por controle em hardware real.
- [ ] Verificar quais adaptadores ISDB-Tb USB funcionam realmente com Linux e com sinal brasileiro.
- [ ] Validar HDMI-CEC com hardware real; não assumir que funciona por uma porta HDMI comum.
- [ ] Persistência de sistema/configurações além dos canais e favoritos, incluindo decisão explícita sobre como guardar perfis de rede de forma segura.
- [ ] Assistente de IA local e opcional: ainda está somente no plano.
- [ ] Aprimoramento perceptual/super-resolução de vídeo por IA: ainda está somente no plano e depende de benchmark.
- [ ] Integração com serviços pagos: ainda não implementada; depende de APIs/SDKs oficiais, autenticação e licenças do provedor.
- [ ] Atualizações de sistema com assinatura, rollback e fluxo de release para usuários finais.
- [ ] Validação final da linha KTV Orsay em TV física ou decisão de congelar esse protótipo.

## 6. Roadmap recomendado por prioridade

### P0 — Validar a Alpha 0.21 no equipamento real

1. Inicializar a ISO em um pendrive conectado ao PC, sem instalar o Linux no disco interno.
2. Confirmar imagem HDMI, áudio, Wi-Fi/Ethernet, navegação por mouse/teclado e desligamento seguro.
3. Assistir à mesma transmissão Pluto por 60–120 minutos. Registrar se há travamento, áudio sem vídeo, encerramento ou reconexão; verificar também a tentativa automática de modo compatível quando aplicável.
4. Simular uma perda breve de rede e verificar a recuperação; depois testar Q, Parar e troca de canal para garantir que o KTV não reabra uma sessão cancelada.
5. Testar canais pessoais, catálogo público, importação M3U e arquivos locais.
6. Testar teclado virtual em busca, endereço e formulários; conferir símbolos, arraste e fechamento/abertura.
7. Testar backup/restauração em um pendrive de dados separado e confirmar que o sistema não formata nem altera a unidade de boot.
8. Se houver receptor USB ISDB-Tb, buscar canais locais e registrar chipset/driver; se houver CEC, identificar o adaptador utilizado.
9. Se houver falha de boot/gráficos, coletar o relatório de diagnóstico antes de mudar parâmetros permanentemente.

**Critério de aceite:** todos os testes devem registrar o hardware, a versão, o resultado e, quando falhar, o relatório/log relevante. CI verde sozinho não conclui esta etapa.

### P1 — Estabilidade e qualidade de canais

- Executar testes prolongados e de reconexão da Pluto; corrigir falsos positivos de travamento sem reiniciar vídeo pausado.
- Validar em hardware o fallback automático de modo compatível da Alpha 0.21 e medir se ele resolve casos de áudio sem vídeo sem causar sobrecarga.
- Manter o catálogo de fontes autorizadas, com ID estável, origem/proveniência, categoria, EPG e validação.
- Ampliar a quantidade de canais apenas após validar a fonte e a permissão de reprodução; separar metadados de programação de URLs de vídeo.
- Unificar o guia XMLTV/EPG quando houver fonte confiável, com tratamento de horários antigos e dados ausentes.
- Testar e documentar quais perfis de qualidade realmente ajudam cada tipo de stream sem causar sobrecarga.

### P2 — Raspberry Pi ARM64

1. Definir o modelo exato (Pi 4 ou Pi 5), RAM, armazenamento e periféricos.
2. Criar uma imagem ARM64 separada, com kernel, bootloader, drivers e pipeline gráfico apropriados.
3. Medir H.264/HEVC, resolução, FPS descartados, uso de CPU/RAM, temperatura e estabilidade.
4. Validar Wi-Fi, saída HDMI, áudio, mouse, teclado virtual, persistência e desligamento.
5. Só depois comparar filtros de imagem e possível super-resolução opcional; nunca ativar IA se ela prejudicar a fluidez.

### P2 — Navegador, teclado e acessibilidade

- Validar o navegador verde com mouse, teclado físico e controle a distância.
- Testar o teclado virtual em todas as entradas, com letras, números, pontuação e símbolos.
- Melhorar foco, voltar/avançar, feedback de pesquisa e comportamento em páginas que bloqueiam incorporação.
- Manter o navegador separado do player de canais; não usar raspagem de páginas para remover anúncios ou proteções.

### P3 — Assistente local de IA (planejado)

**Fase A:** assistente determinístico, sem modelo, para abrir seções, filtrar canais e explicar diagnósticos.  
**Fase B:** avaliar um modelo GGUF pequeno opcional com execução local e limites de CPU/RAM.  
**Fase C:** acessibilidade/voz acionada por botão e preferências locais somente com consentimento.

Requisitos de segurança: nenhuma execução arbitrária de shell, nenhuma senha enviada ao modelo, serviço apenas em loopback, ação sensível sempre confirmada e funcionamento completo do KTV quando a IA estiver desligada.

### P3 — Provedores de TV por assinatura

- Investigar APIs/SDKs, autenticação e incorporação permitida por cada provedor.
- Integrar apenas provedores que autorizem o uso no KTV OS.
- Não extrair tokens, copiar streams privados, contornar DRM ou remover anúncios/controles do serviço.
- Se não existir integração autorizada, manter o canal fora do catálogo reproduzível.

### P3 — KTV Orsay

- Executar o teste controlado de abertura de widget no Smart Hub com o pacote mínimo.
- Diferenciar falha de sincronização, falha ao iniciar widget e falha de player.
- Decidir com base no resultado se o desenvolvimento Orsay continua ou se a prioridade fica integralmente no KTV OS via HDMI.

### P4 — Distribuição e manutenção

- Estabelecer versionamento e notas de versão para cada Alpha.
- Publicar artefatos em releases estáveis, com checksum e instruções de verificação.
- Projetar atualizador seguro com assinatura, validação, rollback e consentimento.
- Revisar logs, diagnósticos e política de persistência para minimizar dados pessoais.
- Fazer revisão de segurança antes de recomendar exposição à rede ou uso permanente.

## 7. Build, testes e como reproduzir

Notas desta melhoria: [Fallback automático de vídeo — Alpha 0.21](../ktv-os/docs/PLAYBACK_FALLBACK_021.md)

### Verificação automatizada

O workflow **KTV Legacy and OS tests** executa testes do servidor/widget Orsay, testes Python do KTV OS, verificação sintática JavaScript e validação dos scripts de build.

Comandos locais úteis:

- Testes KTV OS: `python -m unittest discover -s ktv-os/tests -v`
- Testes do repositório: `python -m unittest discover -s tests -v`
- JavaScript: `node --check ktv-os/app/app.js`
- Teclado: `node --check ktv-os/app/osk.js`
- Navegador verde: `node --check ktv-os/app/browser-green.js`
- Build script: `bash -n ktv-os/linux-live/build-iso.sh`
- Checagem do empacotamento: `bash ktv-os/linux-live/build-iso.sh --check`

### Última ISO verificada

- Workflow: https://github.com/kardecallan566/KTV/actions/runs/40762109771
- Artefato: `KTV-OS-Alpha-0.21-amd64`
- Arquitetura: AMD64 para PC Intel/AMD
- Estado: build concluído com sucesso; o workflow também conferiu o checksum SHA-256.
- Retenção informada pelo GitHub: até 04/11/2026, aproximadamente 20:28 UTC.

A ISO Alpha 0.21 inclui a tentativa automática e limitada de decodificação compatível para alguns casos de áudio sem vídeo. O artefato tem retenção limitada e pode expirar. O build e a suíte automatizada passaram, mas a validação física com GPU, codecs, streams e TV do usuário continua pendente.

## 8. Documentos técnicos relacionados

- [Plano geral antigo do KTV OS](../ktv-os/docs/ROADMAP.md) — contém histórico das primeiras versões; este documento passa a ser o resumo consolidado de estado atual.
- [Linux Live e criação da ISO](../ktv-os/linux-live/README.md)
- [Recuperação Pluto TV](../ktv-os/docs/PLUTO_RECOVERY_019.md)
- [Player integrado e TV aberta](../ktv-os/docs/INTEGRATED_PLAYER_017.md)
- [Antena USB ISDB-Tb](../ktv-os/docs/ANTENNA_ISDBTB_018.md)
- [Integração Rei dos Canais](../ktv-os/docs/REIDOS_GUIDE_020.md)
- [Planejamento de IA local](../ktv-os/docs/AI_ASSISTANT_PLAN.md)
- [Planejamento de qualidade de vídeo no Raspberry Pi](../ktv-os/docs/VIDEO_QUALITY_RPI_PLAN.md)
- [Diagnóstico da Samsung Orsay](./TESTE_REFERENCIA_ORSAY.md)

## 9. Princípios do projeto

1. O KTV OS deve ser um ambiente de TV simples, rápido e controlável por mouse, teclado ou periféricos compatíveis.
2. Priorizar fontes gratuitas, oficiais ou autorizadas; nunca confundir uma URL pública com autorização de retransmissão.
3. Não prometer disponibilidade perpétua de streams externos.
4. Não prometer qualidade superior à resolução/qualidade da fonte.
5. Não contornar DRM, autenticação, controles de acesso ou anúncios dos provedores.
6. Não instalar o sistema no disco interno, alterar firmware da Samsung ou formatar USB sem ação explícita do usuário.
7. Manter IA e melhorias experimentais opcionais; a reprodução e as funções básicas precisam funcionar sem elas.
8. Tratar resultados de CI, teste físico e disponibilidade externa como evidências diferentes e documentar cada uma separadamente.
