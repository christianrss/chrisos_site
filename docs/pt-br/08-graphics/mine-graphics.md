---
id: mine-graphics
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - GAMES/MINE/MINE.CC
  - GAMES/MINE/GEN.CC
  - GAMES/MINE/PLAY.CC
  - GAMES/MINE/CUBE.CC
  - GAMES/MINE/SKY.CC
  - GAMES/MINE/UI.CC
  - kernel/gfx/voxel.c
  - kernel/gfx/voxel.h
  - kernel/lang/clvm_sys.c
  - tools/test_chunk_mesh.c
  - tools/test_mine_spawn_view.c
symbols:
  - paint_world
  - boot_gfx
  - gen_world
  - voxel_world_draw
  - voxel_set
  - draw_mob
depends_on:
  - textures
  - clipping
  - software-3d
related:
  - mine-chris
  - depth-buffer
  - triangle-rasterization
---

# Pipeline gráfica do Mine Chris

## Escopo

Mine Chris é um workload de integração da pilha 3D software original do ChrisOS. O jogo não renderiza o mundo voxel pela API programável Gfx3D/VirGL criada posteriormente. Em vez disso, o código ChrisC/CLVM controla câmera, mundo voxel global, atlas procedural de texturas, iluminação fixed-function, meshes float, z-buffer e UI 2D por meio de syscalls gráficas.

Um frame de gameplay segue aproximadamente:

    estado do player/actors
        -> cam(...)
        -> sky_frame()
        -> world()
        -> draw_mob(...) para actors
        -> ui_hud()

Este capítulo documenta essa composição. A estrutura voxel, o algoritmo de clipping, o sampler de textura e o rasterizador de triângulos são descritos em capítulos próprios; aqui o foco é como Mine Chris integra esses subsistemas em um frame.

## Viewport lógico

O jogo chama `viewport(800, 600)` durante o boot.

Menus, HUD, inventário e crosshair são posicionados diretamente nesse espaço lógico. O crosshair fica em torno de (400,300), e o teste de regressão de câmera também considera Y=300 como a linha central da tela.

A syscall de viewport da CLVM tenta aplicar as dimensões pedidas e volta ao tamanho padrão de jogo caso a operação falhe. Largura e altura ficam disponíveis ao guest por syscalls gráficas adjacentes.

## Ordem do frame

`paint_world` primeiro atualiza a câmera usando o actor zero, que representa o player.

A câmera usa X/Z do player e Y do player + 1,5, além de yaw e pitch.

Depois são executados `sky_frame`, `world` e, por fim, os draws dos actors não-player.

O HUD é composto depois de `paint_world`.

Essa ordem é importante:

1. o background do céu é estabelecido;
2. luz e offsets animados de textura são atualizados;
3. o mundo voxel renderiza e estabelece depth;
4. meshes dos actors são testados contra esse depth;
5. HUD e menus entram como overlays 2D.

Alterar a ordem pode modificar occlusion ou sobrescrever camadas já renderizadas.

## Convenção da câmera

O player nasce próximo de X=72 e Z=80 e tem Y ajustado para o topo do terreno + aproximadamente 1,15.

A câmera fica outros 1,5 unidades acima da origem do actor.

As convenções de movimento e look estão explícitas em `PLAY.CC`.

Movimento para frente usa:

    vx += sin(yaw) * speed
    vz -= cos(yaw) * speed

Com yaw zero, o forward aponta para Z negativo.

O source comenta explicitamente que pitch positivo olha para baixo porque a convenção do vetor forward em math3d usa seno negativo no eixo Y. Como delta Y do mouse também é positivo para baixo na tela, o jogo soma esse valor ao pitch.

Pitch é limitado a -50..50 graus.

## Evidência de regressão da câmera

`tools/test_mine_spawn_view.c` fixa uma convenção que já foi suscetível a erro de sinal.

O teste usa tela 800×600, câmera em (72,11,80), yaw zero e pitch zero.

Um ponto de chão um passo à frente em Z negativo precisa projetar abaixo de Y=300.

Um ponto alto na mesma direção precisa projetar acima de Y=300.

O teste não valida toda a câmera do jogo, mas fixa a orientação do horizonte e a direção forward esperada.

## Modelo de céu

Mine Chris não usa skybox geométrico.

`sky_frame` calcula uma hora a partir de ticks mais um bias e preenche toda a área 800×600 com uma cor plana.

Horas 6 até 17 são dia.

Horas 16 até 18 ativam chuva.

Dia, chuva e noite usam cores de fundo diferentes.

O céu é, portanto, um backdrop 2D barato colocado antes da geometria 3D com depth.

## Iluminação dinâmica

A posição da luz também depende do tempo.

O jogo calcula uma direção semelhante ao sol a partir de seno/cosseno de hora×15 graus.

Durante o dia usa luz mais forte, quente e com Y mais alto.

À noite usa intensidade menor, cor mais fria e posição mais baixa.

Esses valores entram pela syscall de light e alimentam o estado fixed-function de shading usado por faces voxels texturizadas e meshes float.

Como a luz é atualizada antes do mundo, todas as faces visíveis daquele frame usam o novo estado.

## Offset animado de textura

`sky_frame` também calcula:

    wave = ticks % 100
    tex_ofs(wave / 100, 0.04)

O subsystem de textura aplica esse offset global somente ao slot que o renderer considera animado.

Assim, Mine Chris obtém um material em movimento sem regenerar geometria voxel ou UVs.

Como o estado é global, ele pertence ao setup de frame e não a cada face individual.

## Dimensões do mundo

O engine voxel define:

    CHUNK_N = 16
    WORLD_CX = 8
    WORLD_CY = 4
    WORLD_CZ = 8

O volume completo é 128×64×128 voxels dividido em 256 chunks.

Cada bloco ocupa um byte.

IDs são clampados para 0..15 e zero representa vazio.

## Região criada pelo jogo

`gen_world` constrói apenas uma parte artesanal do volume.

A maior parte do terreno fica aproximadamente entre X 48..102 e Z 52..99, com estruturas chegando a alturas na faixa dos teens.

O helper `putb` restringe writes a X/Z 1..126 e Y 1..60.

Isso deixa uma margem interna em relação aos limites completos do engine.

Terreno, água, pontes, árvores, torre, pickups e objetivos são construídos por sucessivas escritas de voxels.

## Invalidação de chunks

Cada `voxel_set` grava o bloco e marca o chunk correspondente como dirty.

Se o voxel estiver na borda do chunk, o chunk vizinho naquela direção também é marcado.

Isso é necessário porque uma face pertencente a um chunk pode aparecer ou desaparecer quando um bloco adjacente de outro chunk muda.

Quebrar e colocar blocos não precisa de uma API separada de mesh: alterar o voxel já agenda os rebuilds adequados.

## Representação do chunk mesh

Um chunk mesh é uma lista de faces expostas, não um vertex/index buffer tradicional.

Cada `MeshFace` armazena X/Y/Z locais, número da face e block ID.

O rebuild percorre todas as 16³ posições do chunk.

Para cada bloco não vazio, verifica as seis posições vizinhas.

A face só é armazenada se o vizinho naquela direção estiver vazio.

Faces internas entre blocos sólidos são eliminadas.

## Capacidade de faces

A lista começa com capacidade 64 e dobra quando necessário.

O crescimento para em:

    FACE_CAP_MAX = 8192

Se o chunk já atingir esse máximo, novas faces não podem ser adicionadas e o rebuild termina antes de representar tudo.

A API atual não expõe um diagnóstico detalhado para esse cenário.

Um chunk patológico com área superficial muito alta pode, portanto, ser truncado.

## Rebuild lazy

Todos os chunks começam dirty na inicialização.

`voxel_world_draw` só chama `rebuild_chunk` quando o chunk está dentro da região aproximada da câmera e continua dirty.

Após o rebuild, o mesh é reutilizado até uma alteração futura do voxel invalidá-lo.

`tools/test_chunk_mesh.c` valida isso: depois do primeiro draw captura `voxel_mesh_rebuilds()`, renderiza novamente sem mudanças e exige que a contagem permaneça igual.

## Seleção grosseira de visibilidade

O renderer não faz frustum culling real de chunks.

Ele constrói uma região AABB centrada na câmera:

    X = câmera ±48
    Y = câmera ±32
    Z = câmera ±48

e clampa os limites ao mundo.

Chunk totalmente fora desse volume é ignorado.

Chunk dentro do volume é processado mesmo quando está atrás da câmera ou fora da projeção final.

O design troca precisão de culling por iteração simples e limitada.

## Reconstrução do quad

As faces armazenadas não contêm arrays de vertices.

Para cada `MeshFace` visível, `face_verts` reconstrói quatro corners world-space conforme a posição do bloco e uma das seis orientações.

A normal vem da mesma tabela ±X/±Y/±Z.

A normal é transformada pela view matrix como direção e normalizada.

As UVs são fixas:

    (0,1)
    (1,1)
    (1,0)
    (0,0)

O quad é dividido em dois triângulos de origem.

## Conversão para camera space

Os quatro corners world-space são transformados pela view matrix.

Cada posição camera-space é guardada junto com U/V em `ClipV`.

Isso permite que o clipping opere simultaneamente na geometria e nas coordenadas de textura.

A iluminação usa a normal transformada; a projeção usa as posições transformadas.

## Clipping da near plane

Cada triângulo é clipado contra:

    z em camera space = 0.08

Vertex está dentro quando Z >= 0,08.

Quando uma aresta cruza o plano, X, Y, Z, U e V são interpolados linearmente no ponto de interseção.

O resultado contém zero, três ou quatro vertices.

Três vertices produzem um triângulo rasterizado.

Quatro produzem dois.

É clipping geométrico real para faces voxel, diferente de paths antigos que apenas rejeitam triângulo quando um vertex não projeta.

## Projeção e rasterização

Cada vertex depois do clipping passa por `project_view`.

Se algum vertex do polígono resultante não puder ser projetado, o polígono é abandonado.

Screen X/Y, software depth, UV, block ID e normal transformada seguem para `tri_fill_tex`.

Esse rasterizador faz z-test, sampling de textura e iluminação.

## Mapeamento de material

No mundo voxel, block ID é enviado diretamente como texture ID.

O jogo gera materiais dentro do range 0..15 do engine.

Assim, o byte armazenado no voxel funciona simultaneamente como identidade de gameplay e seleção de textura/material para o world renderer.

Actors seguem outra convenção: no `meshf`, valores 16+ são interpretados como texture IDs com offset 16, enquanto valores menores usam caminhos de palette/cor fixa.

## Lifecycle do z-buffer

`voxel_world_draw` chama:

    math3d_set_screen(w,h)
    zbuf_set_size(w,h)
    zbuf_clear()

antes de iterar pelos chunks.

Cada chamada a `world()` começa, portanto, um novo depth pass do mundo voxel.

A syscall CLVM de world também prepara o z-buffer do contexto antes de chamar o renderer, mas o clear interno do voxel world é o reset decisivo.

## Occlusion dos actors

Os actors são desenhados depois de `world()` via `meshf`.

O path float de mesh configura o tamanho do z-buffer, mas não o limpa internamente.

Dessa forma, triângulos de actors são testados contra o depth deixado pelo mundo voxel.

Terreno pode ocultar mobs e projectiles.

Qualquer path novo inserido entre mundo e actors não deve limpar o z-buffer se a mesma composição for desejada.

## Geometria dos actors

`CUBE.CC` define oito vertices de uma pequena caixa de aproximadamente 0,8 unidade de largura e altura.

`draw_mob` renderiza essa geometria em doze triângulos via `meshf`.

Kinds diferentes reutilizam o mesmo mesh com translation, yaw e material/cor diferentes.

A aparência vem mais do material e movimento que de meshes distintos.

## Animação dos actors

Alguns actors recebem bobbing vertical por `anim_eval1`.

O Y passado para `draw_mob` é modificado; a geometria em si não é deformada.

Outros states aplicam deslocamentos verticais maiores.

A animação fica, portanto, fora do sistema de chunks e não exige skinning ou atualização per-vertex.

## Interação de gameplay e gráficos

Break/place e algumas ações de charge consultam ou alteram o mundo voxel diretamente.

Quebrar escreve zero no bloco.

Colocar escreve um material ID.

Como `voxel_set` marca chunks dirty, o próximo frame visível reconstrói a geometria afetada automaticamente.

O estado gráfico permanece sincronizado ao gameplay por meio da própria API voxel.

## Chuva

Chuva não é geometria 3D.

Quando ativa, `ui_hud` desenha 24 linhas 2D.

A posição X depende do índice e de ticks.

Essas linhas aparecem depois do mundo e não usam depth.

É uma solução barata, mas significa que chuva não é ocultada por telhados ou terreno.

## HUD e overlays

O HUD mostra hora, fase, notificações, crosshair, hotbar, FPS e chuva.

O crosshair usa duas linhas curtas e um pixel central aproximadamente em (400,300).

Pause e inventory são retângulos e texto no mesmo espaço 2D.

Esses elementos não passam pela projeção 3D nem pelo z-buffer.

## Fronteira CLVM

Mine Chris executa dentro da CLVM.

Syscalls de kernel expõem light state, texture state, voxel set/get, world draw, viewport, helpers matemáticos e operações de mesh.

Antes de operar voxels, a camada de syscall chama `voxel_for(ctx)`, que utiliza o mecanismo global de ownership.

Somente um application slot pode controlar o mundo voxel por vez, exceto se já for o owner atual.

Isso evita que guests diferentes modifiquem simultaneamente o único mundo global.

## Syscall de world draw

A syscall prepara o z-buffer do contexto e verifica ownership do voxel world.

Com ownership válido, chama `voxel_world_draw` usando o pixel buffer e as dimensões lógicas do guest.

Falha de ownership ou rendering propaga erro.

A simples função guest `world()` esconde, portanto, uma pipeline kernel relativamente extensa.

## Evidência de testes

`test_chunk_mesh.c` cria piso 24×24 mais alguns blocos, renderiza em 320×200 e exige mais de 500 pixels não zero.

Também exige mais de oito cores não zero diferentes, fornecendo evidência indireta de variação por textura/iluminação.

O primeiro draw precisa causar rebuild; o segundo sem mudanças não pode aumentar a contagem.

`test_mine_spawn_view.c` valida separadamente a orientação da câmera no viewport 800×600 do jogo.

Juntos, os testes cobrem renderer voxel local e convenções de visão específicas do Mine.

## Limitações atuais

O world path do Mine é software nesta revisão.

Visibilidade de chunks usa AABB em vez de frustum.

Não há occlusion culling nem greedy meshing.

A geometria de chunk mantém um record por face exposta.

A interpolação UV do `tri_fill_tex` legado permanece affine depois do near clipping.

Somente a near plane recebe polygon clipping.

Chunks extremos podem atingir o limite de 8192 faces.

Chuva é overlay 2D.

Actors usam meshes simples.

O mundo voxel é global, não per-scene/per-context.

## Consequências de performance

A geração do mundo é principalmente custo inicial.

Em steady state, o frame é dominado por traversal dos chunks na região visível, rebuilds dirty, reconstrução de faces, transformação pela view, near clipping, projeção e rasterização texturizada.

Edit de bloco normalmente invalida um chunk, mas edit na fronteira pode invalidar vários.

As maiores oportunidades de otimização são frustum culling real, greedy meshing, batching de faces e, futuramente, migração do mundo para o renderer programável com suporte a GPU.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Mine Chris é tratado como workload de integração entre câmera, voxel, clipping, textura, shading, z-buffer, meshes, CLVM e UI 2D, e não como um engine de rendering separado.
