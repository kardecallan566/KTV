# Fallback automático de vídeo — KTV OS Alpha 0.21

## Objetivo

Reduzir casos em que um canal de TV apresenta áudio, mas o mpv não confirma uma saída de vídeo utilizável. A Alpha 0.21 adiciona uma tentativa automática e limitada de abrir novamente a transmissão em modo de decodificação compatível.

## Como funciona

- A interface consulta a telemetria local do mpv durante a reprodução.
- Quando há uma faixa de áudio, mas a faixa/saída de vídeo continua ausente por seis ciclos de diagnóstico (aproximadamente 12–15 segundos), o KTV OS tenta uma única vez o modo compatível.
- O fallback automático vale apenas para canais dos catálogos público, Pluto TV e comunitário.
- Não é executado quando o player informa que a mídia está pausada.
- Se a tentativa automática falhar, o usuário ainda pode iniciar a tentativa manual pelo botão de modo compatível.
- O modo compatível desativa a decodificação por hardware e usa saída X11; pode aumentar o uso de CPU e não é necessariamente melhor em todos os computadores.

## Limites e privacidade

Isto é uma heurística determinística baseada em telemetria do player, **não um recurso de IA**. A detecção de ausência de vídeo não prova DRM nem identifica de forma infalível a causa. O KTV OS não contorna DRM, autenticação, restrições do provedor nem direitos de reprodução. O sistema não envia telemetria para serviços externos.

Canais pessoais, arquivos locais e fontes não classificadas como catálogos de TV não recebem essa tentativa automática, para evitar reiniciar streams que podem ser apenas áudio.

## Validação manual recomendada

1. Iniciar um canal público, Pluto ou comunitário que normalmente apresente áudio sem imagem.
2. Confirmar que a tentativa ocorre apenas após vários ciclos de diagnóstico e que a transmissão reabre em modo compatível.
3. Confirmar que a reprodução normal não é reiniciada quando vídeo e áudio estão funcionando.
4. Pausar a mídia e confirmar que não ocorre fallback durante a pausa.
5. Testar uma playlist pessoal e um arquivo local para confirmar que não há tentativa automática.
6. Medir CPU e estabilidade no hardware real; o modo por software pode ser mais pesado.

Os testes automatizados verificam sintaxe e regressões do projeto, mas não substituem a validação física com a GPU, os codecs e os streams usados pelo usuário.
