---
id: software-3d
lang: pt-br
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/math3d.c
  - kernel/gfx/mesh.c
  - kernel/gfx/mesh.h
  - kernel/gfx/voxel.c
  - kernel/gfx/voxel.h
  - kernel/gfx/tri.c
  - kernel/gfx/zbuf.c
  - kernel/gfx/tex.c
  - kernel/gfx/shade.c
  - kernel/gfx/scene.c
  - kernel/gfx/tile.c
  - kernel/gfx/gfx3d_ctx.c
  - kernel/lang/clvm_sys.c
  - tools/test_mesh.c
  - tools/test_cube_mesh.c
  - tools/test_cube_mesh_f.c
  - tools/test_chunk_mesh.c
  - tools/test_scene.c
symbols:
  - mesh_draw
  - mesh_draw_f
  - mesh_transform
  - voxel_world_draw
  - voxel_set
  - voxel_get
  - voxel_claim
  - voxel_release
  - scene_visible
  - scene_draw
depends_on:
  - textures
  - depth-buffer
related:
  - parallel-raster
  - gfx3d-api
  - mine-graphics
---

# Renderer 3D software

## Escopo

O ChrisOS não possui um único renderer 3D software monolítico. Há vários caminhos montados sobre matemática, rasterização, depth, textura e iluminação compartilhadas.

Os principais são o mesh legado armazenado em memória CLVM, o mesh float, o renderer voxel por chunks e o renderer leve de scene/nodes.

Eles compartilham infraestrutura, mas não possuem exatamente o mesmo contrato. Clipping, ownership de clear do z-buffer, formato da geometria e paralelização diferem entre os caminhos.

## Pipeline conceitual

A sequência geral é:

```text
geometria
  -> model transform
  -> view transform
  -> visibility / clipping
  -> projection
  -> triangle rasterization
  -> depth test
  -> texture / lighting
  -> framebuffer
```

Isso descreve a arquitetura e não uma única função.

O mesh legado pula clipping geométrico verdadeiro. O voxel implementa near clipping. A scene usa uma representação projetada simples em vez de um scene graph geral de meshes arbitrários.

## Estado global versus contexto

Módulos legados mantêm globals para câmera, dimensões, z-buffer ativo, light state, texture slot e offsets.

`Gfx3DCtx` armazena snapshots de view, shade e texture state.

Carregar um contexto copia seus valores para os globals antes do draw.

Esse desenho permite migrar para contexts sem reescrever de uma vez todas as funções de baixo nível.

Ele não torna o renderer automaticamente reentrante ou thread-safe.

## ABI do mesh CLVM

`mesh_draw` lê a geometria diretamente da memória da VM.

O layout é:

```text
V vertices:
  int32 x
  int32 y
  int32 z

T triangles:
  int32 i0
  int32 i1
  int32 i2
```

Cada vértice ocupa 12 bytes e cada triângulo mais 12 bytes para os índices.

As coordenadas inteiras são convertidas por `MODEL_SCALE`.

## Validação de entrada

`mesh_ok` exige VM e framebuffer válidos, pelo menos três vértices e um triângulo.

Os limites são:

```text
MESH_MAX_V = 2048
MESH_MAX_T = 4096
```

O endereço-base precisa ser não negativo e toda a região vertices+indices precisa caber na memória da VM.

Cada índice também é validado antes de ser usado.

Dados inválidos fazem a função retornar -1 em vez de ler fora da VM.

## Arrays globais de staging

Projected X/Y/depth, flags de visibilidade, posições world e índices filtrados ficam em arrays globais fixos.

Isso evita alocação em cada draw.

Ao mesmo tempo, duas chamadas simultâneas de mesh reutilizariam os mesmos arrays.

A implementação atual pressupõe serialização ou exclusão em nível superior.

## Transform em mesh_draw

`mesh_draw` configura screen size e z-buffer, depois limpa depth.

Ele gera a view matrix e uma rotação Y a partir do ângulo inteiro recebido.

A composição é:

```text
view * rotation
```

Cada vértice é convertido para float e enviado a `project_vertex`.

## Regra de visibilidade do mesh legado

`project_vertex` falha quando Z transformado é <=0.

O vértice é marcado como invisível.

Na montagem de triângulos, qualquer primitive que referencie um vértice invisível é descartada inteira.

Isso é primitive rejection, não clipping.

Um triângulo cruzando a câmera pode desaparecer abruptamente.

## Clear interno em mesh_draw

`mesh_draw` chama `zbuf_clear` dentro da própria função.

Cada chamada inicia uma depth frame nova.

Isso é conveniente para um demo isolado, mas interfere na composição: se objeto B é desenhado depois de A usando `mesh_draw`, B limpa o depth de A.

A função não é, portanto, uma primitive natural de scene com múltiplos objetos sem mudar ou encapsular esse lifecycle.

## Tile path automático

Em build freestanding, quando:

```text
w * h >= 640 * 400
```

o mesh legado usa `tile_mesh_raster`.

Resoluções menores iteram os triângulos e chamam `tri_fill`.

O threshold é uma política interna de performance, não configuração pública.

## ABI do mesh float

`mesh_draw_f` usa a mesma ideia estrutural, mas interpreta cada componente de vertex como float IEEE-754 na memória CLVM.

Os índices permanecem int32 depois do array de vertices.

A chamada também recebe translation e yaw do modelo.

## Composição das matrizes

O caminho float monta:

```text
model = translation * rotation_y
mvp   = view * model
```

Cada vertex também é transformado separadamente para world space.

Essas posições world são usadas no cálculo das normals geométricas dos triângulos.

## mesh_draw_f não limpa depth

Ao contrário de `mesh_draw`, `mesh_draw_f` configura o tamanho do z-buffer, mas não chama `zbuf_clear`.

Isso permite desenhar vários meshes float no mesmo depth frame, desde que o caller tenha feito clear do buffer correto antes.

A diferença entre as duas APIs é semântica e não apenas o tipo numérico dos vertices.

A documentação não deve afirmar que todo draw de mesh limpa depth.

## Cálculo de normals

Para cada triângulo aceito:

```text
e0 = world[b] - world[a]
e1 = world[c] - world[a]
normal = normalize(cross(e0,e1))
```

Há um normal geométrico por triângulo.

O ABI não contém authored vertex normals.

Logo, smooth shading real entre vertices compartilhados não está representado pelo formato.

## Cor e textura no mesh float

Com `color < 16`, o caminho usa RGB derivado da paleta e aplica shading com a normal da face.

Com `color >= 16`:

```text
texid = color - 16
```

e chama o caminho texturizado.

Os UVs fornecidos são fixos:

```text
(0,0)
(1,0)
(0,1)
```

Não são lidos do mesh.

## Consequência do vertex format mínimo

A memória do mesh guarda posições e índices, mas não UV, normal, vertex color ou material.

A textura float usa um mapping triangular canônico repetido em toda primitive.

Isso demonstra a pipeline, mas não consegue representar um asset real com unwrap próprio.

Um formato futuro precisa carregar atributos adicionais.

## Borda de texture ID

Colors 16..31 mapeiam para os dezesseis texture slots.

Valores maiores geram `texid > 15`.

O sampler trata ID explícito inválido usando o slot global selecionado.

Assim, um material codificado incorretamente pode depender do estado global em vez de falhar de maneira explícita.

É um alvo claro de hardening.

## mesh_transform

`mesh_transform` é um helper diferente do draw.

Ele lê uma matriz 4×4 float da memória da VM e transforma in-place uma lista de vertices.

Nesse helper, os vertices usam a representação inteira escalada.

A região da matriz e a região de vertices são validadas antes da alteração.

A função não projeta nem rasteriza.

## Dimensões do mundo voxel

Chunks possuem lado 16.

O mundo define:

```text
8 chunks em X
4 chunks em Y
8 chunks em Z
```

Isso resulta em:

```text
128 × 64 × 128
```

cells.

O array de blocks é alocado lazily.

## Ownership do voxel world

O subsystem possui `voxel_claim(slot)` e `voxel_release(slot)`.

Somente um slot pode possuir o world por vez, exceto quando o mesmo owner faz reclaim.

É um mecanismo simples para impedir que duas aplicações CLVM manipulem livremente o mesmo estado global pelo caminho esperado.

Não é isolamento completo de memória, mas torna ownership explícito.

## IDs dos blocks

`voxel_set` valida as coordenadas.

ID negativo vira zero.

ID acima de 15 vira 15.

Zero representa espaço vazio.

IDs não zero também funcionam como texture IDs durante o render.

## Dirty propagation

Mudar um block marca seu chunk como dirty.

Se o block fica numa borda do chunk, o chunk vizinho correspondente também fica dirty.

Isso é necessário porque uma face do vizinho pode aparecer ou desaparecer.

O rebuild é adiado até um draw precisar daquele chunk.

## Extração de faces

`rebuild_chunk` percorre todas as 16³ cells.

Para cada block não zero, verifica seis neighbors.

Uma face é adicionada apenas se o neighbor estiver vazio ou fora do world.

Faces internas entre blocks sólidos desaparecem antes da rasterização.

A lista de faces começa pequena e pode crescer até:

```text
FACE_CAP_MAX = 8192
```

por chunk.

## Crescimento do chunk mesh

Quando a lista enche, um array maior é alocado, as faces são copiadas e o anterior é liberado.

O crescimento parte de 64 e dobra até o limite.

Se kmalloc falhar ou a capacidade máxima já tiver sido atingida, `mesh_push` falha e o rebuild para.

O caminho não oferece ao caller final um diagnóstico rico do motivo.

## Janela em torno da câmera

`voxel_world_draw` restringe o trabalho a uma região aproximadamente:

- ±48 em X;
- ±32 em Y;
- ±48 em Z.

Chunks totalmente fora são pulados.

Esse é um culling espacial grosso antes do custo por face.

## Pipeline da face voxel

Cada face armazenada é reconstruída como quatro corners world-space.

A normal da face é transformada para view space.

Os corners passam para camera space e recebem os UVs fixos do quad.

O quad vira dois triângulos.

Cada um passa por near clipping, projection, rasterização texturizada e depth test.

## Near clipping

O voxel usa:

```text
near = 0.08
```

Uma aresta que cruza esse Z gera novo vertex com posição e UV interpolados.

Por isso uma face parcialmente atrás do near plane pode continuar parcialmente visível.

Esse comportamento é mais completo que o primitive rejection do mesh legado.

## Clear em voxel_world_draw

`voxel_world_draw` chama `zbuf_clear` internamente.

Assim como `mesh_draw`, assume ownership de uma depth frame nova.

Se um caller quiser combinar voxel com meshes já desenhados, esse clear precisa ser considerado na arquitetura.

## Mapeamento de material voxel

Block IDs visíveis 1..15 vão diretamente para `tri_fill_tex`.

O atlas procedural funciona como tabela de materiais.

Cada face usa a textura inteira 0..1.

Não existe scale de UV por block, sub-retângulo de atlas ou material object externo.

## Modelo de iluminação

`shade_phong` implementa um modelo Phong-like pequeno.

A normal de entrada é normalizada.

Os coeficientes são:

```text
ka = 0.22
kd = 0.70
ks = 0.28
```

O specular usa uma potência fixa 16 construída por squaring.

É um renderer didático/experimental e não physically based.

## Cache da luz/view

A implementação guarda vetores normalizados em cache.

O cache é atualizado quando light state muda ou quando a posição da câmera muda.

Yaw/pitch sem mudança de posição não forçam a mesma atualização, pois o view vector simplificado deriva da posição.

Isso evidencia as aproximações atuais do lighting.

## Scene subsystem

`scene.c` possui:

```text
SCENE_MAX = 32
```

nodes.

Cada node armazena mesh ID, posição inteira, yaw e color.

No draw freestanding atual, o mesh ID não é enviado ao renderer genérico.

Cada node visível é representado por um triângulo projetado simples.

Portanto a scene ainda é uma camada leve de demo/organização, não um scene graph geral de meshes.

## Culling da scene

`scene_in_frustum` aproxima yaw usando quatro regiões.

A função calcula forward e side e rejeita nodes atrás ou muito fora de uma wedge frontal.

É object culling aproximado.

Não é clipping de seis planos homogêneos.

`scene_visible` percorre linearmente os 32 slots.

## Bandas paralelas

No build freestanding, a imagem é dividida em até quatro bandas horizontais.

Cada banda é um job.

Os jobs percorrem todos os nodes visíveis, porém `tri_fill_clip` limita cada worker ao seu intervalo Y.

Isso cria ownership de pixels por banda e evita competição direta entre as bandas.

É um padrão mais simples que triangle jobs arbitrários no mesmo tile.

## Animation keys

A scene possui dezesseis slots de keyframe.

`anim_sample` procura o key anterior e o seguinte em relação ao tempo.

Position e yaw são interpolados linearmente com aritmética inteira.

A animação atua sobre transform do node, não implementa skinning ou deformação de vertices.

## Contenção de falhas

Mesh retorna -1 para layout inválido na VM ou índice ilegal.

Voxel init pode falhar se não conseguir alocar o block array.

O crescimento de faces pode parar por allocation failure ou face cap.

As rotinas de rasterização geralmente apenas deixam de desenhar e não retornam códigos ricos.

Por isso a camada em que ocorre a falha precisa ser identificada durante debugging.

## Estrutura de performance

Os custos principais podem ser separados:

| Etapa | Custo |
|---|---|
| transformar/projetar vertices | O(V) |
| validar/filtrar triangles | O(T) |
| rasterização | O(bounding pixels) |
| rebuild de um chunk | O(16³ * 6) |
| scene visibility | O(32) |
| animation sample | O(16) |
| texture sample comum | O(1) |

Depois do culling, quantidade de pixels e faces visíveis tende a dominar.

## Evidência executável

`tools/test_mesh.c` exige que um triângulo vindo da memória CLVM produza pixels.

`tools/test_cube_mesh.c` monta um cube com oito vertices e doze triangles no formato inteiro, aplica rotação e exige mais de 2.000 pixels.

`tools/test_cube_mesh_f.c` usa o formato float e `mesh_draw_f`, exigindo mais de 2.000 pixels e cobertura em mais de 20 colunas.

`tools/test_chunk_mesh.c` cria blocks, renderiza mais de 500 pixels com várias cores e confirma que um segundo draw sem mudanças não aumenta o número de rebuilds.

`tools/test_scene.c` cobre culling e interpolation de animation keys.

## O que ainda não é provado

Os testes atuais não fixam composição de vários meshes em depth compartilhado, a diferença de clear entre `mesh_draw` e `mesh_draw_f`, todos os casos do near clipper, saturação da face cap, fallback de material inválido ou isolamento concorrente dos globals.

Eles são evidência forte de bring-up, mas não uma suite de conformidade completa.

## Regressões recomendadas

Uma hierarquia futura pode combinar testes puros de math, raster/depth, texture/shade determinísticos, checksums de framebuffer por mesh, cenas com múltiplos objetos e testes voxel perto do near plane.

Failure paths também devem fornecer endereços de VM inválidos, índices fora da faixa e pressão de alocação de chunk mesh.

Para concorrência, repetir o mesmo frame com múltiplos workers e comparar checksum ajuda a detectar races visuais.

## Ordem de debugging

Quando um mesh desaparece, primeiro diferencie erro de validação de erro de visibilidade.

Depois verifique camera-space Z e se o caminho faz clipping ou rejection.

Em seguida examine screen coordinates, coverage e z-buffer.

Somente depois de confirmar fragmento visível faz sentido investigar texture e lighting.

Para voxel, conferir `voxel_mesh_rebuilds` ajuda a separar problema de rebuild de problema de rasterização.

## Limitações atuais

O renderer mistura globals e context save/load, possui vertex format mínimo, textura afim e lighting simples.

O mesh legado usa rejection no near plane.

A scene é simplificada.

Algumas entry points limpam depth por conta própria, enquanto outras exigem que o caller faça isso.

Apesar disso, a pilha já forma um renderer CPU executável integrado à CLVM e ao ChrisOS.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, descrevendo mesh, voxel e scene como caminhos distintos com infraestrutura compartilhada.
