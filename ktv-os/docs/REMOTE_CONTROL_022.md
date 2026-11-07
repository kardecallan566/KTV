# Controle remoto KTV OS — resposta rápida (0.22)

## Mudanças
- O receptor de comandos da interface da TV usa **long polling com despertar por evento**. Em vez de consultar o servidor 25 vezes por segundo, mantém uma única requisição pendente; ao tocar em uma tecla no celular, a fila notifica a requisição imediatamente.
- O tempo de espera do endpoint é limitado a 25 s e o navegador reabre a consulta após cada resposta. Erros transitórios usam uma pausa curta de 500 ms.
- O servidor continua validando PIN/token e a lista de ações permitidas. Long polling só entrega comandos de navegação já autenticados; mouse permanece no endpoint de comando direto.
- A tela remota foi redesenhada para celular: cartões, navegação em grade, atalhos com ícones, touchpad ampliado, botões maiores, feedback de toque/vibração e tempo de confirmação HTTP.
- O mouse acumula deslocamentos e envia em intervalos de 30 ms, evitando excesso de chamadas simultâneas.
- O servidor deixa de gravar no terminal cada movimento do mouse (tráfego de alta frequência), reduzindo I/O e ruído no Raspberry Pi.

## Testes
`tests/test_remote_control.py` verifica despertar imediato, resposta sem espera para eventos já disponíveis e timeout limitado.

## Limites
O indicador em milissegundos no celular mede a confirmação HTTP do servidor (recebimento do comando), não o tempo de renderização/execução da ação na TV. A execução da navegação depende de a interface KTV estar aberta no computador/TV. O teste automatizado não substitui validação física no Raspberry Pi e no celular.
