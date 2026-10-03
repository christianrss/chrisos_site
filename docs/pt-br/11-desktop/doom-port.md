---
id: doom-port
lang: pt-br
title: "Port do Doom: trazendo um motor de jogo C real para o ChrisOS"
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - GAMES/DOOM/DOOM.CC
  - GAMES/DOOM/ENGINE.LST
  - GAMES/DOOM/MAIN.CC
  - GAMES/DOOM/I_CHRIS.CC
  - GAMES/DOOM/I_VIDEO.CC
  - GAMES/DOOM/I_INPUT.CC
  - GAMES/DOOM/I_SOUND.CC
  - GAMES/DOOM/W_FILE.CC
  - tools/doom_qemu_long_smoke.py
  - tools/doom_qemu_smoke.py
  - tools/test_doom_jit_smoke.c
  - tools/test_doom_path_pcs.c
  - tools/test_doom_compile.c
  - tools/test_doom_engine.c
symbols:
  - doomgeneric_Create
  - DG_Init
  - DG_DrawFrame
  - DG_SleepMs
  - DG_GetTicksMs
  - DG_GetKey
  - I_InitGraphics
  - I_FinishUpdate
  - I_StartTic
  - poll_key
  - W_OpenFile
  - W_Read
  - W_CloseFile
depends_on:
  - chrisc-clvm
  - input-routing
  - gfx2d
  - chrisfs
---

# Port do Doom: trazendo um motor de jogo C real para o ChrisOS

O trabalho com Doom no ChrisOS é mais do que uma demonstração de jogo. Ele funciona como teste de integração para compilador/runtime, framebuffer, entrada, sistema de arquivos, alocação de memória, temporização e a camada de compatibilidade necessária para executar uma base C preexistente de tamanho significativo.

Há dois alvos diferentes na revisão analisada e eles não devem ser confundidos.

`GAMES/DOOM/DOOM.CC` é um pequeno bring-up em ChrisC. Ele abre um WAD do Doom, procura `PLAYPAL`, mantém um framebuffer indexado de 320×200, aceita um conjunto pequeno de teclas e desenha um padrão sintético em movimento. Ele **não** executa o motor completo do Doom.

`GAMES/DOOM/ENGINE.LST` representa o caminho do port real. Ele combina bibliotecas e adaptadores do ChrisOS com um grande conjunto de fontes em `third_party/doomgeneric_src/doomgeneric`, terminando no `MAIN.CC` específico do ChrisOS. Portanto, `ENGINE.CLV` é o artefato relevante ao discutir o port do motor completo.

## Por que Doom é um teste útil de sistemas

Um motor Doom real exercita várias camadas ao mesmo tempo:

1. compatibilidade da linguagem C e ABI suficiente para um programa legado grande;
2. memória dinâmica e serviços equivalentes a partes da biblioteca padrão;
3. acesso binário a arquivos WAD;
4. framebuffer indexado estável de 320×200;
5. atualização de paleta;
6. tradução de eventos de teclado;
7. relógio e mecanismo de espera;
8. ponto de entrada e modelo de argumentos específicos do host.

Assim, uma falha depois do boot do kernel não é necessariamente um problema gráfico. Ela pode estar no compilador, na semântica da CLVM, no modelo de memória, na libc disponível, no filesystem, nos adaptadores da plataforma ou em uma suposição feita pelo código original do Doom.

## Dois alvos de validação distintos

Os testes do repositório diferenciam o demo pequeno do motor completo.

`tools/test_doom_compile.c` compila `GAMES/DOOM/DOOM.LST`, correspondente ao alvo de bring-up menor. É cobertura válida do compilador, mas não prova a compilação de `ENGINE.LST`.

`tools/test_doom_engine.c` é o gate específico do motor. Ele lê `ENGINE.LST`, reserva buffer de saída de 8 MiB, chama `chrisc_compile_files_ex` e exige que o callback de progresso cubra todos os fontes da lista.

Essa diferença evita a afirmação ambígua "Doom compila": ela pode se referir ao demo ou ao port muito maior do engine.

## Composição do build

`ENGINE.LST` começa com implementações do ChrisOS para string, stdio, stdlib, ctype e math. Depois adiciona os adaptadores do Doom para o ChrisOS:

- `I_CHRIS.CC`
- `I_SOUND.CC`
- `I_VIDEO.CC`
- `W_FILE.CC`
- `I_INPUT.CC`

Em seguida entram os módulos do DoomGeneric: estado do jogo, eventos, mapas, inimigos, renderização, menus, WAD, zone allocator e muitos outros subsistemas. `MAIN.CC` fecha a lista como ponto de entrada.

Essa estrutura é importante: o ChrisOS não está reimplementando a jogabilidade do Doom do zero. O port procura preservar o motor original e substituir as bordas que dependem do sistema operacional.

## Entrada do programa e argv sintético

`MAIN.CC` constrói manualmente um vetor de argumentos equivalente, aproximadamente, a:

```text
doom -iwad GAMES/DOOM/DOOM1.WAD -mb 16
```

Depois atribui `myargc` e `myargv`, inicializa a camada DoomGeneric com `DG_Init()` e chama `D_DoomMain()`. O ponto de entrada ChrisC continua chamando `doomgeneric_Tick()` e cedendo execução com `wait(1)`.

Essa construção explícita evita depender de um ABI convencional de inicialização de processos Unix e torna determinísticos o caminho do WAD e a configuração de memória usada no ambiente atual.

## Memória e pressupostos de execução

Ferramentas do engine evidenciam que `ENGINE.CLV` é uma carga CLVM muito maior que demos comuns.

Vários diagnósticos instanciam a imagem com 32 MiB de memória de VM. Separadamente, o argv sintético fornece `-mb 16` ao próprio Doom. São camadas diferentes: os 32 MiB pertencem ao harness/VM; `-mb 16` é argumento interpretado pelo motor.

A documentação não deve tratar os dois números como um único limite de heap.

O engine pode atravessar caminhos interpreter ou JIT conforme a configuração do runtime. Portanto, além da compilação, a correção depende da semântica das instruções CLVM e da equivalência do JIT para esse programa.

## Caminho de vídeo

O backend do ChrisOS usa a representação clássica do Doom:

- largura de 320 pixels;
- altura de 200 pixels;
- um byte por pixel;
- buffer de 64.000 bytes;
- paleta de 256 entradas com três bytes por entrada.

`I_InitGraphics()` aponta `I_VideoBuffer` para `DG_Screen`. `I_SetPalette()` encaminha a paleta para `setpal()`. `I_FinishUpdate()` chama `DG_DrawFrame()`, que termina em `fb_blit()`.

O fluxo principal é:

```text
renderizador do Doom
    ↓
I_VideoBuffer / DG_Screen (320×200 indexado)
    ↓
DG_DrawFrame()
    ↓
fb_blit()
    ↓
subsistema gráfico do ChrisOS
```

Não há aqui uma API de GPU moderna. O objetivo do backend é fornecer uma fronteira pequena de compatibilidade baseada em framebuffer indexado.

## Detalhes do ABI de vídeo

A fronteira de vídeo possui invariantes concretos.

`DG_Screen` contém exatamente 64.000 bytes e `I_ReadScreen` copia exatamente 64.000. `I_InitGraphics` define `I_VideoBuffer = DG_Screen`, largura 320 e altura 200.

Transporte de paleta é separado de pixels. `I_SetPalette` envia a paleta de 768 bytes a `setpal`; o screen buffer continua contendo índices de cor de um byte.

Vários hooks de configuração são stubs. `I_GetPaletteIndex`, por exemplo, retorna zero em vez de procurar RGB, e callbacks de título/configuração não formam um backend completo de vídeo desktop.

Esses no-ops importam porque código upstream pode chamá-los mesmo que o caminho comum não dependa fortemente do resultado.

## Tradução de entrada

O caminho do motor completo não depende de `DG_GetKey()` para a jogabilidade. Essa função atualmente não retorna eventos. Em vez disso, `I_StartTic()` consulta o estado das teclas do ChrisOS e converte transições em eventos do Doom por meio de `D_PostEvent()`.

`poll_key()` compara o estado atual com `key_was[128]`. A transição de solta para pressionada produz key-down; de pressionada para solta produz key-up. Isso evita tratar uma tecla mantida como uma nova pressão a cada consulta.

O mapeamento inclui Escape, Enter, Tab, Backspace, Space/use, Ctrl/fire, Shift, setas, WASD, números de armas e Y/N para diálogos de confirmação.

É uma adaptação entre dois modelos: o ChrisOS fornece estado consultável de teclas, enquanto Doom espera um fluxo de eventos.

## Temporização

`DG_GetTicksMs()` converte `ticks()` para milissegundos assumindo uma base de 60 Hz:

```text
milissegundos = ticks × 1000 / 60
```

`DG_SleepMs()` faz a aproximação inversa e usa `wait()`, garantindo pelo menos um tick. É uma ponte de bring-up, não um temporizador de alta resolução.

## Memória do estado de input

O tradutor de bordas armazena estado anterior em `key_was[128]`. `poll_key(sc, code)` indexa essa tabela diretamente com os scan codes fixos usados pelo adaptador.

Todos os scan codes atualmente mapeados ficam abaixo de 128. Adicionar futuramente um código >=128 exige ampliar a estrutura ou validar o índice.

Cada transição cria um `dg_event` local: type 0 para key-down, type 1 para key-up; o key code traduzido é copiado para `data1` e `data2`.

Isso é uma adaptação concreta de ABI/event model, não apenas "suporte a teclado".

## Acesso ao WAD

`W_FILE.CC` adapta a interface de arquivos WAD para a API ChrisC. `W_OpenFile()` usa `fopen()`, obtém o tamanho com `fsize()`, aloca um pequeno descritor e preserva o file descriptor inteiro. `W_Read()` usa `fseek()` e `fread()`. `W_CloseFile()` fecha o arquivo e libera o wrapper.

O repositório analisado contém `DOOM1.WAD` e também um `DOOM1.MINI.WAD` muito pequeno. O ponto de entrada do motor completo seleciona explicitamente `GAMES/DOOM/DOOM1.WAD`.

O demo separado em `DOOM.CC` usa outra estratégia: carrega o WAD inteiro em memória, percorre o diretório, localiza o lump `PLAYPAL` e copia 768 bytes de paleta. Isso valida parsing de WAD e transporte da paleta, mas não deve ser descrito como o motor completo.

## Semântica de falha no I/O do WAD

`W_OpenFile` rejeita `fopen` falho, erro de alocação e tamanho não positivo. Se malloc falhar, fecha o descriptor já aberto antes de retornar.

`W_Read`, porém, confia no offset e comprimento recebidos e delega a `fseek`/`fread`; não compara por conta própria `offset + buffer_len` com o tamanho armazenado do WAD. A camada WAD do engine deve solicitar ranges válidos.

O adaptador também não faz memory mapping: `mapped` permanece nulo e as leituras são baseadas em file descriptor.

Isso mantém a ponte pequena, mas não acrescenta uma segunda camada de range checking contra requests inesperados.

## Estado do áudio

Áudio ainda não está implementado no backend do Doom analisado. `I_SOUND.CC` fornece os símbolos esperados pelo motor, porém inicialização, reprodução, música, canais e precache são essencialmente no-ops. As funções de início de som retornam valores de falha e `I_SoundIsPlaying()` retorna falso.

Essa é uma limitação específica do port e não uma afirmação de que o ChrisOS inteiro seja incapaz de produzir áudio.

## Shims de compatibilidade e serviços nativos

O port demonstra uma regra útil para levar software existente a um novo sistema operacional: preservar o contrato esperado pela aplicação e construir o menor adaptador possível no lado do host.

| Expectativa do motor | Ponte no ChrisOS |
|---|---|
| framebuffer indexado | `DG_Screen` / `I_VideoBuffer` |
| apresentação do frame | `fb_blit()` |
| paleta | `setpal()` |
| eventos de teclado | `key()` + `D_PostEvent()` |
| tempo | `ticks()` |
| espera/yield | `wait()` |
| acesso ao WAD | `fopen/fseek/fread/fsize` |
| heap | alocação do runtime ChrisC |
| som/música | atualmente stubs |

Assim, a maior parte do código do Doom permanece sem conhecer detalhes específicos do ChrisOS.

## Evidência executável disponível

A árvore contém vários gates com força crescente:

- `test_doom_engine.c`: compila o `ENGINE.LST` completo e verifica progresso de todos os fontes;
- `test_doom_path_pcs.c`: carrega `ENGINE.CLV`, fornece 32 MiB à VM e executa interpreter registrando checkpoints de PC/SP;
- `test_doom_jit_smoke.c`: faz parse, compilação JIT e slices repetidos de execução;
- `doom_qemu_smoke.py`: inicializa ChrisOS em QEMU e captura serial;
- `doom_qemu_long_smoke.py`: ativa `SYS/SMOKE.DOOM`, executa uma janela longa e define sucesso como abertura de `DOOM1.WAD`, evidência de startup e ausência dos fatal markers configurados.

Esses arquivos definem níveis de evidência. A presença deles não significa que todos foram executados com sucesso nesta atualização da documentação. Resultado de teste deve ser registrado separadamente da descrição do gate.

## O que o port atual demonstra

A existência de `ENGINE.CLV` e a extensa lista de fontes mostram que o toolchain ChrisC/CLVM consegue processar uma base DoomGeneric muito maior do que o pequeno demo isolado. Também existem bindings concretos para vídeo, entrada, tempo e arquivos WAD.

Isso **não** prova, isoladamente, que todos os caminhos do jogo estejam corretos, que todos os mapas possam ser concluídos, que o áudio funcione ou que o motor tenha compatibilidade de produção. Gerar um artefato compilado e validar completamente sua execução são marcos diferentes.

## Depurando o bring-up

Nesta fase, o diagnóstico deve seguir as fronteiras entre subsistemas, e não apenas o sintoma visual.

Uma sequência prática é:

```text
1. Confirmar que MAIN.CC iniciou.
2. Confirmar integridade do argv sintético.
3. Confirmar retorno de DG_Init.
4. Confirmar abertura e tamanho plausível de DOOM1.WAD.
5. Confirmar que W_Read lê corretamente o cabeçalho.
6. Confirmar que D_DoomMain avança além da inicialização do WAD.
7. Confirmar I_InitGraphics e I_VideoBuffer.
8. Confirmar eventos produzidos por I_StartTic.
9. Confirmar I_FinishUpdate chegando a fb_blit.
10. Só então investigar corrupção de renderização/jogabilidade.
```

Isso separa falhas de compilador/runtime, dados e adaptadores de dispositivos.

## Considerações algorítmicas e de desempenho

Em 320×200, `I_ReadScreen` custa O(64.000) por cópia completa. A apresentação também movimenta uma superfície indexada de 64.000 bytes antes do caminho gráfico posterior de composição/escala.

Polling de input é O(K) no conjunto fixo de teclas mapeadas por tic. Leitura WAD é proporcional ao tamanho solicitado mais o custo de seek/read do filesystem.

Os shims são propositalmente pequenos; os custos maiores continuam no renderer, gameplay, zone allocator e WAD logic upstream. Doom deve ser perfilado como workload end-to-end, não apenas pelos adapters.

## Limitações conhecidas na revisão analisada

O estado atual contém áreas deliberadamente incompletas:

- som e música são stubs;
- `DG_GetKey()` não fornece diretamente a entrada do jogo;
- temporização depende da hipótese de tick a 60 Hz;
- vídeo está fixado em saída indexada de 320×200;
- vários hooks de configuração de vídeo são no-ops;
- `DOOM.CC` é um demo visual/WAD, não o motor completo;
- a compilação de `ENGINE.CLV` não deve ser confundida com validação completa em runtime.

Registrar essas fronteiras é importante. Isso indica exatamente onde o desenvolvimento deve continuar, em vez de esconder comportamento incompleto atrás da frase genérica “Doom foi portado”.

## Lição arquitetural

Doom é relevante para o ChrisOS porque força subsistemas independentes a concordarem sobre contratos reais. Programas pequenos conseguem validar uma syscall ou uma função de framebuffer isoladamente. Doom combina memória, arquivos, eventos, tempo, renderização e uma grande aplicação C em uma única carga de trabalho.

Por isso, o port é melhor entendido como benchmark de integração do sistema: quanto mais próximo o motor não modificado chega de uma execução correta, mais completo e compatível se torna o ambiente de userspace ChrisC/CLVM.
