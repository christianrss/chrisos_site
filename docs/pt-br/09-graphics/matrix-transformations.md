---
id: matrix-transformations
lang: pt-br
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/math3d.h
  - kernel/gfx/math3d.c
  - kernel/gfx/mesh.c
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d_ctx.h
  - kernel/gfx/shader/glsl/mvp.vert
  - tools/test_math3d.c
  - tools/test_math3d_view.c
  - tools/test_gfx3d_abi.c
  - tools/test_mine_spawn_view.c
symbols:
  - vec3f_set
  - vec3f_dot
  - vec3f_cross
  - vec3f_norm
  - mat4f_identity
  - mat4f_mul
  - mat4f_rotate_x
  - mat4f_rotate_y
  - mat4f_rotate_z
  - mat4f_scale
  - mat4f_translate
  - mat4f_perspective
  - mat4f_ortho
  - mat4f_transform
  - mat4f_transform4
  - mat4f_to_glsl
  - mat4f_normal3
  - math3d_view
  - project_view
  - project_vertex
depends_on:
  - gfx2d
related:
  - clipping
  - triangle-rasterization
  - software-3d
  - gfx3d-api
  - shaders-csir
---

# Transformações matriciais e espaços de coordenadas

## Escopo

O ChrisOS concentra sua matemática 3D em `kernel/gfx/math3d.c`. A camada oferece vetores, matrizes 4×4, construção de câmera/view, projeção e conversão entre a representação de matriz da CPU e a representação usada pelo caminho GLSL/`gfx3d`.

O fato arquitetural mais importante é que existem atualmente dois pipelines relacionados, mas diferentes.

O caminho software mais antigo transforma vértices para espaço de câmera e faz uma divisão direta pelo `z` positivo. O caminho mais novo de `gfx3d`/shader suporta model-view-projection homogêneo e mantém quatro componentes através de `mat4f_transform4`.

Documentar ambos como se fossem uma única pipeline esconderia diferenças reais.

## Convenção de coordenadas

`math3d_view` explicita a convenção:

- yaw 0 olha para -Z;
- +X é direita da câmera quando yaw é zero;
- pitch positivo olha para baixo;
- a câmera não possui roll.

O vetor forward é:

```text
f.x = sin(yaw) * cos(pitch)
f.y = -sin(pitch)
f.z = -cos(yaw) * cos(pitch)
```

O vetor right permanece horizontal:

```text
r = (cos(yaw), 0, sin(yaw))
```

Up é derivado de `r × f` e normalizado.

Essa convenção explica por que delta Y positivo do mouse pode aumentar pitch e fazer a câmera olhar para baixo sem representar um erro de sinal.

## Operações vetoriais

`Vec3f` contém três floats. A biblioteca implementa soma, subtração, dot product, cross product, comprimento e normalização.

`vec3f_norm` possui política explícita para vetor degenerado. Quando o comprimento é menor ou igual a `1e-8`, a função não mantém o vetor original e não retorna erro. Ela substitui o valor por:

```text
(0, 1, 0)
```

Callers que precisem preservar vetor zero precisam de outro contrato.

Para valores comuns, a normalização divide os componentes pelo comprimento Euclidiano calculado com `__builtin_sqrtf(dot(v,v))`.

## Representação das matrizes

`Mat4f` contém 16 floats em ordem row-major.

As rotinas tratam vetores matematicamente como vetores coluna. Por isso, translation ocupa a última coluna das três primeiras linhas:

```text
m[3]   -> X
m[7]   -> Y
m[11]  -> Z
```

`mat4f_transform` aplica uma posição `(x,y,z,1)` calculando somente as três primeiras linhas.

`mat4f_transform4` calcula as quatro linhas e recebe explicitamente `w`. É a operação adequada quando coordenadas homogêneas são relevantes.

## Multiplicação

`mat4f_mul(o,a,b)` calcula:

```text
o = a × b
```

com loops fixos de linha, coluna e quatro termos internos.

O resultado é calculado em uma matriz temporária antes da atribuição a `*o`. Assim, o destino pode coincidir com um dos operandos sem ser parcialmente sobrescrito durante o cálculo.

Como é sempre 4×4, o custo é constante: 64 contribuições de multiply-add mais overhead dos loops.

A ordem importa. Para um vetor coluna em que o objeto deve primeiro rotacionar e depois transladar:

```text
model = translation × rotation
world = model × local
```

É a composição usada por `mesh_draw_f`.

## Identity, scale e translation

`mat4f_identity` zera as 16 posições e define a diagonal principal como 1.

`mat4f_scale` começa por identity e altera os componentes X/Y/Z da diagonal.

`mat4f_translate` começa por identity e grava translation em 3, 7 e 11.

Os construtores criam matrizes completas; não acumulam implicitamente transformações anteriores. Composição é feita explicitamente por `mat4f_mul`.

## Matrizes de rotação

Há construtores separados para X, Y e Z.

Os ângulos são em graus. As funções trigonométricas usam uma LUT de 0..90 graus e reflexão por quadrante, em vez de `sinf/cosf` do host.

Um detalhe de precisão é relevante: `gfx_sinf` converte o grau normalizado para inteiro antes de acessar a LUT. Não há interpolação entre entradas. Assim, ângulos fracionários são efetivamente quantizados em passos inteiros de grau.

Para a câmera atual isso pode ser aceitável, mas é uma propriedade numérica real.

## Custo do wrapping de ângulo

`wrap_deg` normaliza somando ou subtraindo 360 repetidamente.

Para valores normais de câmera o custo é desprezível. Para valores de magnitude enorme, o tempo cresce com o número de voltas de 360 em vez de usar remainder em tempo constante.

O contrato é orientado a ângulos normais de rendering, não a entradas numéricas arbitrariamente grandes.

## Construção da view matrix

`math3d_cam_set` grava posição, yaw e pitch em estado global.

`math3d_view` deriva forward, right e up, normaliza os vetores necessários e constrói a view row-major.

Cada linha da base recebe um termo de translation igual ao dot negativo entre o vetor da base e a posição da câmera.

Conceitualmente:

```text
view(world) =
[
 right · (world - camera),
 up    · (world - camera),
 fwd   · (world - camera)
]
```

Um objeto à frente da câmera produz Z positivo no caminho software legado.

## Estado global e contexto

A camada matemática mantém câmera e dimensões da tela em globals.

`math3d_state_save` e `math3d_state_load` transferem esses valores por `Gfx3DView`.

O caminho novo `gfx3d_camera` ainda chama o setter global, gera uma view matrix e copia a matriz resultante para o contexto gráfico.

Portanto há uma transição arquitetural: contextos 3D guardam view própria, mas os helpers básicos de câmera ainda não formam uma API completamente isolada por contexto.

Callers concorrentes não devem presumir isolamento automático dos setters globais.

## Projeção software legada

`project_view` recebe um ponto já em espaço de câmera.

Se `z <= 0`, falha, define coordenadas de tela como -1/-1 e depth máximo.

Caso contrário:

```text
sx = width/2  + x * (width/2)  / z
sy = height/2 - y * (height/2) / z
```

Depth é derivado do Z positivo por `depth_to_z`.

É uma câmera pinhole compacta sem FOV explícito; a escala depende diretamente das metades de largura e altura.

## project_vertex no caminho legado

`project_vertex` primeiro aplica `mat4f_transform` e depois usa a mesma divisão por Z.

Embora alguns callers chamem a variável de `mvp`, a função não executa perspective divide homogêneo com quatro componentes. Ela transforma X/Y/Z e divide X/Y pelo Z resultante.

Em `mesh.c`, normalmente recebe:

```text
view × model
```

e não uma matriz de projeção perspectiva completa.

Esse é o modelo correto para o renderer software legado.

## Projeção homogênea

`mat4f_perspective` constrói uma matriz perspectiva de quatro componentes.

A rotina saneia entradas:

- aspect quase zero vira 1;
- near abaixo de `1e-4` vira 0.1;
- far menor ou igual a near vira `near + 1`.

O fator de FOV é cosine/sine do meio FOV, equivalente a cotangent dentro da representação trigonométrica da LUT.

A matriz grava `-1` no termo Z da quarta linha e zero no W final, tornando `w` parte essencial da transformação.

Ela pertence naturalmente a `mat4f_transform4` e shaders, não ao projector legado de três componentes.

## Projeção ortográfica

`mat4f_ortho` recebe left/right, bottom/top e near/far.

Spans próximos de zero são substituídos por 1 para evitar divisão quase nula.

Diferentemente de perspectiva, X/Y não encolhem conforme distância.

## ABI CPU ↔ shader

As matrizes da CPU são row-major, enquanto GLSL normalmente recebe palavras em column-major.

`mat4f_to_glsl` converte o layout:

```text
out[col * 4 + row] = m[row * 4 + col]
```

A matriz matemática não muda; muda apenas a ordem serializada.

`tools/test_gfx3d_abi.c` verifica essa fronteira executando model/view/projection na CPU com `mat4f_transform4` e comparando com o vertex shader software.

É evidência mais forte do que apenas verificar compilação.

## Limitação da normal matrix

`mat4f_normal3` copia o bloco 3×3 superior esquerdo depois da conversão de layout.

Ele não calcula inverse-transpose.

Isso funciona para rotações e determinados casos de escala uniforme, mas uma normal sob escala não uniforme exige matematicamente inverse-transpose.

A documentação de iluminação não deve chamar a implementação atual de normal matrix geral.

## Depth

`depth_to_z` converte depth float positivo para escala inteira semelhante a 16.16:

```text
depth = clip_z * 65536
```

Valores <=0 ou acima de um milhão produzem `0xFFFFFFFF`.

Esse formato pertence ao z-buffer software e não equivale diretamente ao depth normalizado de GPU.

## Comportamento numérico e restrições de ABI

A camada usa `float` de precisão simples. Composições repetidas podem acumular erro de arredondamento, especialmente quando uma transformação existente é multiplicada continuamente em vez de reconstruída a partir de estado canônico do objeto.

A câmera atual normalmente reconstrói a base a partir de posição/yaw/pitch, evitando acumular uma orientation matrix frame após frame. Código de aplicação que multiplique repetidamente a própria model matrix, porém, deve esperar drift normal de ponto flutuante.

A LUT de graus adiciona outra quantização, independente do erro IEEE-754. O caller pode armazenar yaw fracionário, mas `gfx_sinf/gfx_cosf` o avaliam no grau inteiro obtido por truncamento. Logo, o ângulo armazenado e a base efetivamente renderizada podem diferir em resolução sub-grau.

Existe também uma fronteira de layout no ABI de shaders. A matriz row-major da CPU não deve ser enviada como `m[16]` bruto para um contrato que espera palavras column-major. `mat4f_to_glsl` é o ponto canônico de conversão no fonte revisado.

## Ownership de model, view e projection

As três categorias têm owners distintos na API nova.

Model pertence ao objeto/contexto e é configurada por `gfx3d_model`. Posição/orientação da câmera são convertidas em view por `gfx3d_camera`. A mesma chamada cria projection a partir de aspect ratio do target e dos valores FOV/near/far fornecidos.

Quando um programa está ativo, essas matrizes podem ser enviadas a uniforms nomeados como `model`, `view` e `projection`.

Essa separação evita que mover a câmera reescreva geometria local dos objetos e evita que transformar um objeto altere o espaço da câmera.

## Consumidores

A camada é usada por:

- `mesh.c` em model/view e projeção software;
- `voxel.c` para faces em camera space e normals;
- `gfx3d.c` para view/projection por contexto;
- shaders software;
- Mine Chris e sua convenção de câmera;
- testes do ABI CPU/shader.

Isso transforma a matemática em um contrato transversal da pilha gráfica.

## Evidência executável

`tools/test_math3d.c` valida projeção central/lateral, rejeição de ponto atrás da câmera, rotação Y de 90 graus e valores trigonométricos básicos.

`tools/test_math3d_view.c` testa quatro yaws e três pitches. Confirma posição vertical acima/abaixo do aim, direita da câmera e a convenção de pitch positivo para baixo.

`tools/test_mine_spawn_view.c` testa a orientação usada no spawn de Mine Chris e exige ordenação correta entre solo, horizonte e céu.

`tools/test_gfx3d_abi.c` compara CPU e shader para identity, translation, rotações X/Y/Z, scale, camera, yaw, pitch, perspective e ortho.

Em conjunto, os testes cobrem tanto a câmera legada quanto o ABI homogêneo novo.

## Relação com clipping

Transformação e clipping são etapas consecutivas, mas diferentes.

O caminho voxel transforma primeiro world → camera com a view matrix. Somente depois compara Z com o near plane 0.08. Isso permite interpolar novas posições em um espaço linear apropriado antes da divisão perspectiva.

O caminho homogêneo produz posições clip-space com quatro componentes. Nesse modelo, clipping canônico deve acontecer antes do divide por W.

Misturar essas ordens pode produzir interseções incorretas: fazer clipping depois da projeção perde a relação linear original das arestas em 3D.

Essa separação é a razão pela qual o capítulo seguinte trata clipping como contrato próprio.

## Resumo de complexidade

| Operação | Custo |
|---|---:|
| soma/sub/dot/cross vetorial | O(1) |
| normalização | O(1) + sqrt |
| construtor de matriz | O(1) |
| multiplicação 4×4 | O(4³) fixo |
| transform 3D | O(1) |
| transform homogêneo | O(1) |
| projeção | O(1) |
| view matrix | O(1) |
| wrap de ângulo | O(número de voltas de 360°) |

Em rendering, o fator relevante é quantos vértices executam essas operações constantes.

## Invariantes úteis de debugging

Ao investigar uma transformação incorreta, a ordem de diagnóstico mais confiável é separar os espaços.

Primeiro valide o ponto local antes da model matrix. Depois verifique world space após model. Em seguida aplique view e confirme que um objeto à frente produz Z positivo no caminho legado. Somente então aplique projection ou a divisão por Z correspondente.

Também é importante verificar o layout no momento de cruzar CPU e shader. Um resultado correto na CPU pode parecer transposto no shader se o caller ignorar `mat4f_to_glsl`.

Esses passos distinguem erro de ordem de multiplicação, convenção de câmera, sinal de pitch, storage layout e projeção, evitando atribuir todos os sintomas à mesma "matriz errada".

## Limitações atuais

O projector software possui escala implícita em vez de FOV configurável. Pontos com Z não positivo são rejeitados sem clipping poligonal nesse helper. A trigonometria é quantizada em graus inteiros. Câmera/tela ainda possuem estado global. A normal matrix geral por inverse-transpose não existe.

O caminho homogêneo de `gfx3d` é mais convencional, mas ainda coexiste com a pipeline software simples.

## Nota de revisão

Este capítulo foi criado a partir da revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, usando o comportamento observado no fonte e nos testes host. Ele separa deliberadamente a pipeline software em camera space da pipeline homogênea de shaders.
