---
id: mine-chris
lang: pt-br
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - GAMES/MINE/MINE.CC
  - GAMES/MINE/MINE.LST
  - GAMES/MINE/STATE.CC
  - GAMES/MINE/PLAY.CC
  - GAMES/MINE/GEN.CC
  - GAMES/MINE/AI.CC
  - GAMES/MINE/SAVE.CC
  - GAMES/MINE/SKY.CC
  - GAMES/MINE/CUBE.CC
  - GAMES/MINE/UI.CC
  - LIB/BODY.CC
  - LIB/CLIP.CC
  - LIB/ANIM.CC
  - LIB/SIM.CC
  - LIB/HIT.CC
depends_on:
  - input-routing
  - desktop-applications
  - chrisc-clvm
  - software-3d
  - mine-graphics
---

# Mine Chris: um jogo voxel como workload de integração do ChrisOS

Mine Chris é um jogo voxel em primeira pessoa implementado em ChrisC e distribuído como `GAMES/MINE/MINE.CLV`. No currículo da documentação, sua importância não está apenas em ser um jogo: um único programa exercita runtime CLVM, entrada, voxels, 3D por software, simulação, áudio, persistência em filesystem, UI e loop de aplicação.

O fonte revisado é modular no nível de ChrisC. `MINE.CC` inclui bibliotecas compartilhadas de simulação/gráficos e módulos próprios de estado, geração, céu, persistência, IA, gameplay e UI. `MINE.LST`, por outro lado, contém apenas `GAMES/MINE/MINE.CC`; os demais arquivos entram transitivamente pelos `#include` do fonte.

## Estrutura de execução

```text
MINE.CLV
   |
   +-- entrada ------- teclado + mouse relativo/capturado
   +-- simulação ----- atores + colisão + consultas de voxel
   +-- mundo --------- geração voxel + alteração de blocos
   +-- renderização -- câmera + mundo + meshes + HUD
   +-- ambiente ------ relógio + dia/noite + chuva
   +-- áudio --------- tone + PCM
   +-- persistência -- MINE.SAV
   +-- UI ------------ menu + pausa + inventário + HUD
```

O jogo funciona como teste de sistemas porque todos esses caminhos precisam operar em conjunto continuamente.

## Loop principal e modos

`main()` solicita viewport 800×600, inicializa gráficos e começa com `g_mode = 0`. O loop continua até o modo 9.

Modo 0 apresenta o menu. Gameplay usa modo 1, modo 2 representa pausa, modo 3 inventário e modo 5 é usado após a condição de conclusão da torre. Teclas alternam entre esses estados. Durante gameplay ativo, `play_step()` atualiza a simulação, `paint_world()` desenha a cena e `ui_hud()` sobrepõe o estado do jogo.

É uma máquina de estados direta, não um framework geral de cenas.

## Representação de estado

`STATE.CC` define `Actor` com posição, velocidade, yaw, pitch, tipo, estado, timer e bit-fields para chão, água, arco e estado vivo. O pool global possui 16 atores. A entrada zero representa o jogador; as demais são reutilizadas por atores do mundo, pickups e projéteis.

O jogo também mantém inventário de 16 posições, contadores de recursos, flags ambientais, handles de cena/física, buffers de paleta e áudio e um snapshot para respawn em checkpoint.

O tamanho fixo é uma característica desta revisão. Mine Chris não estabelece um ECS ilimitado.

## Geração do mundo voxel

`GEN.CC` constrói um mundo voxel finito e desenhado. `putb()` rejeita coordenadas abaixo de 1 e acima de x/z 126 ou y 60 antes de chamar `voxel()`. `gen_world()` preenche uma região com terreno, água, estruturas, árvores e blocos especiais, marcando depois `g_built` para evitar reconstrução repetida.

O mundo é gerado programaticamente por código determinístico de posicionamento, mas não é um gerador procedural infinito de terreno. O fonte descreve uma área finita de jogo.

## Movimento do jogador e câmera

`spawn_player()` procura o terreno sólido para baixo e posiciona o ator zero acima dele. `play_step()` lê deltas do mouse e teclado, atualiza yaw/pitch e aplica velocidade relativa ao yaw. O pitch é limitado entre -50 e +50 graus.

O próprio fonte registra a convenção: Y positivo do mouse em espaço de tela aumenta pitch porque o vetor frontal 3D usa seno negativo na direção vertical.

O movimento passa por `sim_move()`. O contato com chão é recalculado com `sim_blocked()`, enquanto água é detectada por `voxel_get()` e reduz a velocidade horizontal.

Durante gameplay, o jogo utiliza captura de mouse e movimento relativo, sendo um consumidor prático da infraestrutura de input routing documentada anteriormente.

## Interação com blocos

O jogo remove e posiciona voxels. `break_block()` consulta um ponto à frente do jogador com alcance 2.2, valida o alvo e substitui o voxel por zero. IDs válidos são adicionados ao inventário. `place_block()` converte slots da mão em IDs de bloco, verifica quantidade disponível e só escreve em célula vazia.

Isso demonstra que o mundo voxel não serve apenas à renderização: a lógica do jogo lê e modifica a mesma representação.

## Arco e projéteis

`shoot()` converte carga acumulada em escala limitada entre 0.4 e 2.2. A rotina procura um slot livre de ator, reduz a quantidade de flechas e cria um projétil cuja velocidade deriva de yaw e pitch. A ação também utiliza saída tone/PCM.

Carga alta pode coletar determinados voxels próximos antes da alocação do projétil. Se nenhum slot de ator estiver livre, o projétil não é criado.

O pool fixo produz, assim, um limite observável de recursos e exercita estado limitado no runtime.

## Atores e IA

`boot_actors()` inicializa o pool, cria o jogador e posiciona vários atores/pickups em coordenadas fixas. `AI.CC` atualiza atores que não sejam projéteis ou pickups através de uma pequena máquina de estados dependente de tipo, chuva, fase, distância ao jogador e timer.

O movimento é simples: pequenos componentes de velocidade em x/z e consultas de ocupação voxel. Não existe pathfinding por navigation mesh; trata-se de um sistema compacto de comportamento adequado para exercitar primitivas de simulação.

## Renderização

`paint_world()` posiciona a câmera a partir do ator zero, renderiza céu e mundo voxel e percorre os demais slots. Atores ativos são desenhados por `draw_mob()` com animação vertical e escolha de cor dependentes do estado.

`CUBE.CC` define oito vértices para um pequeno mesh em forma de caixa, inicializa uma transformação identidade e envia o mesh através de `meshf()`.

Mine Chris conecta, portanto, estado de gameplay a geometria e rasterização de baixo nível em vez de depender apenas de assets pré-renderizados.

## Dia, noite e clima

`SKY.CC` deriva a hora do jogo de `ticks()` somado a `g_bias`. O relógio percorre 24 valores. Horas 6 a 17 são dia e chuva é habilitada das 16 às 18.

O caminho de céu altera parâmetros de iluminação e preenchimento de fundo conforme dia/noite/chuva e atualiza offset de textura pelo contador de ticks. `sky_flip()` desloca o bias para alternar faixas de dia e noite.

É um modelo ambiental determinístico, não uma simulação meteorológica.

## Menus, HUD e inventário

`UI.CC` implementa botões testados contra a posição do ponteiro para menu principal e pausa. O menu oferece Jogar, Continuar e Sair. Continuar inicializa o mundo se necessário e tenta `save_read()`.

A pausa oferece continuar, checkpoint, inventário e saída da fase. O inventário mostra quantidades de itens, flechas, madeira e pérolas. O HUD exibe hora, fase, chuva, notificações temporárias, mira, slots da mão e FPS.

A UI é desenhada diretamente com primitivas como `fillrgb()`, `text()`, `line()` e `pixel()`, e não por um toolkit grande de widgets.

## Progressão

O gameplay possui transições explícitas de fase. O estado inicial é fase 1. Obter madeira suficiente e alcançar a região correspondente avança para fase 2; obter pérolas suficientes e chegar ao outro lado avança para fase 3. Alcançar um bloco especial em altura define modo 5, no qual o HUD mostra a conclusão da torre.

Essas regras são lógica de jogo codificada diretamente e não constituem um quest engine genérico.

## Save e checkpoint

`SAVE.CC` mantém dois conceitos. `g_snap` é um snapshot em memória do jogador usado por `respawn()`. `MINE.SAV` é a persistência no filesystem.

`save_pack()` produz uma representação compacta em bytes contendo marcador, fase, posição/yaw convertidos para inteiro, recursos e 16 entradas de inventário. `save_write()` grava 40 bytes em `MINE.SAV`; `save_read()` lê 40 bytes e só aceita os dados quando o primeiro byte é 77.

O formato é deliberadamente pequeno. O código revisado não estabelece versionamento, checksum, substituição atômica, migração de schema ou recuperação robusta de corrupção. Também não persiste todo o mundo voxel mutável nem todo o estado dos atores.

## Áudio

O gameplay chama `tone()` para feedback curto e `pcm_write()` durante o disparo. Mine Chris exercita, portanto, geração simples de tons e um caminho PCM. O pequeno `g_pcm[64]` é inicializado no bootstrap.

O áudio representa integração funcional, não um mixer completo ou sistema de streaming de assets.

## Por que Mine Chris pertence à documentação do sistema operacional

Mine Chris atravessa várias fronteiras de subsistemas em um executável:

```text
entrada -> estado -> simulação -> mutação voxel
                      |
                      v
                câmera/geometria
                      |
                      v
                   gráficos

ChrisFS <-> save             áudio <- eventos do jogo
```

Uma funcionalidade de kernel/runtime pode parecer correta isoladamente e ainda falhar quando combinada com captura de input, simulação contínua, filesystem, renderização e áudio. Um jogo cria pressão integrada que pequenos exemplos unitários não produzem.

## Limitações atuais

A revisão analisada utiliza pool fixo de 16 atores, região voxel finita, pequenas máquinas de estado para IA, bindings numéricos diretos de input, arrays fixos de inventário e save compacto sem versionamento. O fonte não estabelece networking, multiplayer, streaming de terreno, ECS geral, pathfinding sofisticado ou persistência completa de mutações arbitrárias do mundo.

Esses limites também tornam Mine Chris pedagogicamente útil: o caminho completo de entrada para simulação e renderização permanece inspecionável, mesmo exercitando uma parcela substancial da pilha de aplicações do ChrisOS.
