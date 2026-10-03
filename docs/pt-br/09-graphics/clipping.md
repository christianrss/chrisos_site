---
id: clipping
lang: pt-br
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/voxel.c
  - kernel/gfx/math3d.c
  - kernel/gfx/mesh.c
  - kernel/gfx/tri.c
  - kernel/gfx/tri.h
  - kernel/gfx/scene.c
  - kernel/gfx/gfx3d.c
  - LIB/CLIP.CC
  - tools/test_math3d.c
  - tools/test_scene.c
  - tools/test_chunk_mesh.c
symbols:
  - clip_near_tri
  - draw_clipped
  - project_view
  - project_vertex
  - tri_fill_clip
  - tri_fill_u32
  - scene_in_frustum
  - scene_visible
  - clip_aabb
  - clip_ray_aabb
depends_on:
  - matrix-transformations
related:
  - triangle-rasterization
  - depth-buffer
  - software-3d
  - mine-graphics
---

# Clipping, rejeição e fronteiras de visibilidade

## Escopo

A palavra "clipping" aparece em mecanismos diferentes no ChrisOS atual e eles não devem ser tratados como uma única operação.

O renderer voxel faz clipping geométrico real de triângulos contra um near plane. O renderer genérico de mesh software geralmente rejeita o triângulo quando algum vértice projetado está atrás da câmera. O rasterizador restringe iteração de pixels a um retângulo/scissor. O subsistema de scene faz frustum culling aproximado antes do desenho. Separadamente, `LIB/CLIP.CC` contém helpers de colisão de gameplay.

Este capítulo separa esses contratos.

## Por que clipping é necessário

Projeção perspectiva envolve divisão por profundidade.

Quando Z em camera space se aproxima de zero, X/Y projetados podem crescer drasticamente. Um ponto atrás da câmera deixa de representar um ponto visível na direção frontal.

Projetar todos os vértices sem tratamento não forma uma pipeline poligonal completa.

Se um triângulo atravessa o plano da câmera, normalmente queremos preservar a parte visível, criar pontos de interseção e remover somente a região fora do half-space.

Isso é diferente de descartar o triângulo inteiro.

## Convenção do near plane no voxel renderer

`voxel.c` transforma os vértices de cada face para camera space.

O clipper específico usa:

```text
near = 0.08
inside ⇔ z >= near
```

Esse valor pertence ao renderer voxel software. Não é necessariamente o mesmo `znear` configurável do contexto `gfx3d`.

Cada face quad é dividida primeiro em dois triângulos, e cada triângulo é clipado separadamente antes da projeção.

## Atributos ClipV

A estrutura `ClipV` contém:

```text
x, y, z
u, v
```

Preservar U/V é necessário porque criar uma nova borda geométrica sem interpolar textura introduziria descontinuidade.

Normals não são por vértice nessa estrutura. O normal da face é transformado separadamente e fornecido como um único normal para o rasterizador texturizado.

## Algoritmo clip_near_tri

`clip_near_tri` implementa clipping de um triângulo contra um único plano.

Ele percorre as três arestas orientadas:

```text
a = input[i]
b = input[(i+1) mod 3]
```

Cada endpoint é classificado por `z >= 0.08`.

Os casos são:

| a | b | saída |
|---|---|---|
| dentro | dentro | b |
| dentro | fora | interseção |
| fora | dentro | interseção, depois b |
| fora | fora | nada |

O fator da interseção é:

```text
t = (near - a.z) / (b.z - a.z)
```

X, Y, U e V são interpolados pelo mesmo `t`, e Z é definido exatamente como `near`.

É o mesmo princípio de edge processing do Sutherland-Hodgman, especializado para um plano e três vértices de entrada.

## Quantidade de vértices

Um triângulo contra um half-space pode resultar em:

- 0 vértices quando totalmente fora;
- 3 quando totalmente dentro ou quando sobra um canto com duas interseções;
- 4 quando dois vértices originais permanecem e duas interseções são criadas.

Por isso o output fixo possui quatro posições.

Não há alocação dinâmica.

## Re-triangulação

`draw_clipped` ignora resultado com menos de três vértices.

Com três, desenha:

```text
0, 1, 2
```

Com quatro:

```text
0, 1, 2
0, 2, 3
```

Depois todos os vértices passam por `project_view`.

Como interseções recebem Z=0.08 e os vértices preservados estão à frente desse plano, a projeção não deveria receber Z não positivo quando o clipping produziu um polígono válido.

## Interpolação da textura

As interseções interpolam U/V linearmente no parâmetro `t` da aresta em camera space.

Isso mantém continuidade da coordenada de textura na borda criada.

O rasterizador posterior interpola U/V afim em screen space por pesos baricêntricos. Ele não implementa a forma perspective-correct baseada em U/W e V/W.

Clipping geométrico correto e interpolação perspectiva correta são problemas diferentes.

## Fluxo completo da face voxel

```text
face voxel
   ↓
quatro cantos em world space
   ↓
view transform
   ↓
dois triângulos em camera space
   ↓
clip_near_tri(z >= 0.08)
   ↓
polígono de 3/4 vértices
   ↓
project_view()
   ↓
tri_fill_tex()
```

É a implementação mais clara de clipping poligonal real na pilha software atual.

## Mesh legado: rejeição, não clipping

`mesh_draw` e `mesh_draw_f` executam `project_vertex` para cada vértice.

A função retorna falso se Z transformado for <=0.

Na montagem dos triângulos, se qualquer um dos três vértices tiver `g_vis == 0`, todo o triângulo é descartado.

Assim, um triângulo atravessando a câmera pode desaparecer completamente em vez de ser recortado.

É uma estratégia simples de bring-up, mas pode causar popping perto do near plane.

O termo correto aqui é rejeição, não clipping geométrico.

## Near planes não unificados

Há thresholds diferentes.

O voxel usa 0.08. O contexto `gfx3d` inicializa near normalmente em 0.1 e aceita outro valor do caller. O projector legado exige apenas Z>0.

São contratos de pipelines diferentes.

Uma futura unificação deve decidir se voxel software, mesh software e shader/GPU compartilham exatamente a mesma câmera/projeção.

## Clipping em screen space

Depois da projeção, `tri_fill_u32`, `tri_fill_lit` e `tri_fill_tex` calculam bounding box do triângulo.

`clip_box` intersecta essa caixa com:

- o clip rectangle informado;
- limites X do framebuffer;
- limites Y do framebuffer.

Se a interseção for vazia, o rasterizador retorna.

Caso contrário, apenas pixels dentro da caixa resultante são visitados e depois testados pelas funções de aresta.

Isso reduz trabalho e protege acessos de memória, mas não gera novos vértices.

## tri_fill_clip como scissor

`tri_fill_clip` converte um índice de paleta para RGB e chama `tri_fill_u32` com:

```text
clip_x0, clip_y0, clip_x1, clip_y1
```

`tri_fill` comum usa o framebuffer inteiro.

O scene renderer usa retângulos explícitos para dividir a tela em bandas horizontais. Nesse caso, o clipping também determina ownership de escrita entre workers.

Portanto o retângulo funciona de modo semelhante a scissor, e não como clipping poligonal.

## Frustum culling aproximado da scene

`scene_in_frustum` não implementa seis planos homogêneos.

Ele calcula `fwd` e `side` inteiros usando um de quatro quadrantes de yaw.

O objeto é rejeitado se:

```text
fwd + radius < 8
```

ou se a magnitude lateral ultrapassa aproximadamente:

```text
fwd + radius
```

Isso forma uma cunha frontal aproximada.

`scene_visible` percorre os nodes e registra os que passam.

O objetivo é evitar desenho de objetos obviamente irrelevantes, não calcular interseção exata de polígonos com o frustum.

## Culling versus clipping

Culling decide descartar uma primitiva ou objeto inteiro.

Clipping preserva parte da primitiva criando novas bordas.

Exemplos:

- `scene_in_frustum`: object culling;
- `project_vertex(z<=0)` + descarte do triângulo: primitive rejection;
- `clip_near_tri`: geometric clipping;
- `clip_box`: bounding/scissor de pixels.

Terminologia correta ajuda a diagnosticar geometria desaparecendo.

## Backend software de gfx3d

O caminho mais novo executa vertex shader e recebe posições clip-space de quatro componentes.

`soft_tri` rejeita o triângulo se algum `w` estiver muito próximo de zero e então calcula:

```text
ndc_x = x / w
ndc_y = y / w
```

seguido do mapeamento para pixels.

O bounding box resultante é limitado às dimensões do target.

Na rotina inspecionada não existe uma etapa completa de clipping poligonal contra o volume canônico ±X, ±Y, near e far antes do perspective divide.

Essa é uma limitação real do backend software programável atual.

## Caminho de hardware/VirGL

A API `gfx3d` também pode usar backend VirGL/dispositivo.

Nesse caminho, clipping padrão pode ser responsabilidade da pipeline gráfica subjacente, usando posições homogêneas produzidas pelo vertex shader.

Isso não significa que software fallback e hardware possuam comportamento idêntico em todos os edge cases.

## Depth não é clipping

Z-buffer resolve qual fragmento sobrevivente está mais próximo num pixel.

Um fragmento escondido por depth não é a mesma coisa que uma primitiva fora do volume visível.

Erros de near-plane acontecem antes da resolução normal de profundidade.

## LIB/CLIP.CC é colisão de gameplay

`LIB/CLIP.CC` contém `clip_aabb` e `clip_ray_aabb`, usados por Mine Chris e código de física em ChrisC.

`clip_aabb` testa overlap entre cubos axis-aligned descritos por posição e um único tamanho.

Apesar do nome, `clip_ray_aabb` não é clipper poligonal e também não é um teste slab 3D geral de ray/AABB. No caminho com dx não zero, o cálculo de `t` usa apenas direção/intervalo de X.

É helper de gameplay e não deve ser citado como implementação do view-frustum clipper.

## Edge cases de correção

Em `clip_near_tri`, o denominador `b.z - a.z` só é usado quando os valores são diferentes.

Uma aresta cujos dois pontos estão exatamente no near plane é inside/inside e mantém o endpoint.

Uma aresta paralela ao plano com ambos os pontos do mesmo lado não precisa calcular interseção.

Definir o Z gerado exatamente como `near` evita pequenas profundidades negativas na borda por erro numérico da interpolação.

## Escopo dos atributos

O clipper voxel preserva posição e UV.

Ele não interpola normal por vértice, cor, tangent ou varyings arbitrários porque `ClipV` não carrega esses dados.

Um clipper genérico para a pipeline programável precisaria preservar todos os varyings relevantes.

## Complexidade

Para um triângulo e um plano, `clip_near_tri` executa três classificações de aresta: O(1).

O resultado gera no máximo dois triângulos.

Bounding-box clipping do rasterizador também é O(1); o custo posterior depende da área de pixels intersectada.

`scene_visible` é O(N) no número de nodes.

O valor do clipping/culling está principalmente no trabalho de rasterização evitado.

## Evidência executável

`tools/test_math3d.c` confirma que ponto com Z negativo é rejeitado pelo projector legado. Isso prova a regra de rejeição, não clipping poligonal.

`tools/test_scene.c` testa decisões representativas: objeto à frente aceito, atrás rejeitado e objeto muito lateral rejeitado.

`tools/test_chunk_mesh.c` cria voxels, renderiza o mundo duas vezes, exige quantidade significativa de pixels e verifica que chunks sem alteração não são reconstruídos no segundo frame. Como o renderer inclui `clip_near_tri`, há cobertura de integração do caminho.

Entretanto, não existe no conjunto inspecionado um teste dedicado que force diretamente todos os casos do clipper, como um vértice dentro/dois fora e dois dentro/um fora.

## Lacunas recomendadas de validação

Um teste de near plane deveria validar:

- triângulo totalmente dentro;
- totalmente fora;
- um vértice dentro;
- dois dentro;
- vértice exatamente em Z=0.08;
- U/V nas duas interseções;
- winding/ordem da saída;
- continuidade ao triangular um quad clipado.

O backend software de `gfx3d` também precisa de testes de clip-space canônico se parity com GPU for objetivo.

## Limitações atuais

Clipping poligonal de near plane existe apenas em partes do renderer software, principalmente voxel. Mesh legado descarta triângulos parcialmente visíveis. O backend software de shaders não possui uma etapa poligonal completa do clip volume canônico. O rasterizador limita bounding boxes/rectangles. Frustum da scene é aproximado.

Portanto, o código utiliza múltiplos mecanismos de visibilidade desenvolvidos para estágios diferentes do projeto, e não um subsistema único de clipping.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele distingue clipping geométrico, primitive rejection, object culling, raster scissoring e colisão de gameplay conforme o comportamento real do fonte.
