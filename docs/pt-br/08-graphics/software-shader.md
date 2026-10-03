---
id: software-shader
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_exec.c
  - kernel/gfx/shader/sh_api.c
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d.h
  - tools/test_shader.c
  - tools/test_gfx3d_abi.c
symbols:
  - sh_exec_ir
  - sh_soft_vs
  - sh_soft_fs
  - sh_soft_triangle
  - gfx3d_draw
depends_on:
  - csir
  - gfx3d-api
related:
  - tgsi-backend
  - software-3d
  - triangle-rasterization
---

# Backend software de shaders

## Escopo

O caminho programável em software executa o mesmo CSIR verificado que alimenta o backend TGSI/VirGL.

Há duas camadas: `sh_exec_ir`, o interpreter escalar de CSIR, e rasterizadores CPU que executam vertex e fragment shaders ao redor da interpolação de triângulos.

Também existem dois caminhos de triângulo:

- `sh_soft_triangle`, um proof renderer compacto limitado a 128×128;
- `soft_tri` em `gfx3d.c`, usado pelo backend software público do Gfx3D em targets de até 1920×1080.

Ambos são separados do renderer antigo baseado em `tri.c`.

## Estado do interpreter

Cada chamada de `sh_exec_ir` cria um register file local com 96 temporaries de quatro lanes e duas stacks de 32 posições para control flow.

O register file é zerado a cada invocation. Scalars, vectors, values semelhantes a integers e booleans compartilham storage float, seguindo o modelo do CSIR.

Antes da execução, fragment color é zerado, discard é limpo e vertex position recebe o default `(0,0,0,1)` quando esses outputs estão presentes.

O interpreter não mantém temporaries entre vertices ou fragments.

## Control flow estruturado

`IR_IF` testa a lane X. Zero é false; qualquer outro valor é true.

As duas stacks acompanham skip state e estado da branch. Um parent false mantém branches internas skipped. ELSE alterna apenas uma branch cujo parent está ativo. ENDIF remove um nível.

ELSE/ENDIF malformados ou nesting runtime acima de 32 retornam erro defensivamente, embora CSIR verificado já deva impedir esses casos.

`IR_DISCARD` marca o fragment como descartado e encerra a execução imediatamente.

## Movimento de dados

CONST copia values do immediate pool e zera lanes não usadas.

MOV copia a quantidade selecionada de lanes.

SWZ primeiro copia as quatro lanes do source para scratch local antes de escrever o destination. Isso torna seguro um swizzle cujo source e destination sejam o mesmo temporary.

SETLANE altera apenas uma lane e preserva as demais, mantendo a semântica não-SSA documentada no capítulo de CSIR.

## Arithmetic

ADD, SUB, MUL, MIN, MAX e ABS operam component-wise.

DOT acumula três ou quatro lanes conforme o width da instruction e grava lane X.

Comparisons LT, GT, LE, GE, EQ e NE leem valores escalares e produzem 1.0 ou 0.0.

TRUNC converte por cast inteiro de C e armazena novamente como float.

O backend, portanto, implementa integer-like semantics usando o mesmo register file float.

## Reciprocal e RSQ

RCP opera por component.

Input zero produz zero, e não infinito.

RSQ produz zero quando o input não é estritamente positivo. Para values positivos, usa a aproximação local de power com exponent 0.5 e depois reciprocal.

Esses comportamentos são semântica concreta do backend software e podem diferir do host/VirGL em zeros, negative values, infinities ou NaNs.

## Trigonometria local

O backend evita depender de libm.

Sine tenta normalizar o argumento em torno de ±π, com guard de 16 iterações em cada direção, e avalia uma série curta com seis correções.

Cosine é implementado chamando sine com offset de π/2.

É suficiente para o conjunto atual de testes, mas não é uma biblioteca matemática de alta precisão nem deve ser considerada bit-equivalent ao GPU.

## Exponential, logarithm e power

POW possui fast path para expoentes inteiros não negativos menores que 16 usando multiplicação repetida.

Base negativa é suportada apenas nesse caso integral restrito. Com exponent não integral, base negativa retorna zero.

O caminho geral para base positiva usa exponential aproximado de exponent vezes logarithm aproximado.

Exponential clampa input para [-10,10] e usa 16 termos. Logarithm normaliza o valor com loops limitados e usa uma série de 20 termos.

Comparações CPU/VirGL dessas funções precisam usar tolerâncias.

## Matrices

IR_MULMV e IR_MULMM tratam temporaries consecutivos como columns de matrix.

Matrix-vector multiplica cada column pela lane correspondente do vector e acumula o resultado.

Matrix-matrix repete a operação para cada output column.

O interpreter segue a semântica column-major do shader subsystem. Gfx3D converte `Mat4f` CPU para a ordem de shader antes de enviar uniforms.

## Attributes

IR_LOAD_ATTR trata a entrada como oito slots vec4.

No path Gfx3D, `load_attr` converte um vertex bruto em array denso de 32 floats. Primeiro zera tudo; depois copia até quatro float components de cada element do layout para `location*4`.

Locations fora de 0..7 e negative offsets são ignorados.

O loader atual pressupõe elements float. Não decodifica normalized integers, half-floats ou packed vertex formats.

## Uniforms

IR_LOAD_UNI lê arrays de words separados por stage, quatro floats por slot.

Mat3 e mat4 ocupam slots consecutivos.

`sh_soft_vs` recebe words do vertex stage; `sh_soft_fs` recebe words do fragment stage.

A API pública de uniform atualiza ocorrências de mesmo nome em ambos os stages quando necessário, então o backend software observa o mesmo logical program state usado pelo backend VirGL.

## Varyings e remap

IR_STORE_VAR grava um dos oito varying slots.

IR_LOAD_VAR lê um varying do fragment stage e aplica antes o `var_remap` criado pelo linker.

Essa é a mesma relação usada durante geração do TGSI linked.

Assim, a associação vertex-output → fragment-input permanece consistente entre CPU e VirGL.

## Fragment coordinate

IR_LOAD_FCOORD recebe um vec4 montado pelo rasterizador.

Os caminhos software usam:

```text
x = centro X do pixel
y = centro Y do pixel
z = depth software atual
w = 1 / reciprocal-W interpolado
```

Logo, `gl_FragCoord.w` segue essa convenção específica da implementação.

## Texture sampling CPU

IR_SAMPLE chama um sampler nearest/clamp.

U e V são clampados para [0,1].

As coordenadas de texel são:

```text
x = int(u * (width  - 1) + 0.5)
y = int(v * (height - 1) + 0.5)
```

Depois há clamps defensivos dos integers.

Não há bilinear filtering, mipmaps, repeat, mirrored repeat ou anisotropy.

## Byte order da texture

O sampler interpreta quatro bytes por texel e converte para RGBA normalizado:

```text
R = byte2 / 255
G = byte1 / 255
B = byte0 / 255
A = byte3 / 255
```

Isso corresponde ao layout little-endian dos valores 32-bit BGRA-like usados nas public textures do Gfx3D.

Esse sampler não é o antigo `tex_sample` procedural, que possui outras regras de wrapping.

## Wrapper de vertex shader

`sh_soft_vs` exige linked program, attribute input e position output.

Ele chama `sh_exec_ir` com vertex uniforms, sem varying input, sem fragcoord e sem texture.

O caller fornece storage para varyings.

Projection e viewport não são feitos nesse wrapper: projection vem do shader, e viewport vem do rasterizador.

## Wrapper de fragment shader

`sh_soft_fs` executa o CSIR do fragment stage com uniforms, varyings linked, fragcoord opcional, texture opcional e varying remap.

Retorna color e discard state.

Coverage, depth test e packing de pixel ficam fora desse wrapper.

## Proof renderer

`sh_soft_triangle` é o renderer end-to-end usado nos testes do shader subsystem.

A surface é limitada a 128×128.

A função recebe três pointers de attributes já separados. `attr_stride` precisa ser pelo menos quatro, mas na revisão atual não é usado depois porque cada vertex já chegou por pointer próprio.

Um depth buffer float é alocado para a surface inteira em cada chamada.

## Vertex processing

O vertex shader roda três vezes.

Se qualquer W estiver aproximadamente entre ±0.0001, o helper retorna erro.

Caso contrário:

```text
invw = 1 / W
x = (X/W * 0.5 + 0.5) * width
y = (1 - (Y/W * 0.5 + 0.5)) * height
```

Não existe stage de homogeneous clipping.

## Bounding box e samples

Min/max projetados formam bounding box inteira, limitada à surface.

Samples são avaliados em `pixel + 0.5`.

O signed edge denominator é recalculado dentro do pixel loop. Magnitude abaixo de aproximadamente 0.0001 indica triângulo degenerado.

Barycentrics são edge values divididos pelo denominator com sinal.

Pixel é rejeitado se qualquer weight ficar abaixo de -0.001.

Como o sinal do winding é normalizado pelo denominator, ambos os windings podem renderizar. Não há culling nem regra top-left explícita.

## Perspective-correct interpolation

O rasterizador calcula:

```text
iw = b0/w0 + b1/w1 + b2/w2
```

Cada component de varying é:

```text
(b0*v0/w0 + b1*v1/w1 + b2*v2/w2) / iw
```

Todos os oito varying slots e quatro lanes são interpolados em loops fixos, mesmo quando o linked shader usa menos.

É interpolation perspective-correct, diferente do UV affine do antigo `tri.c`.

## Fórmula atual de depth

O depth programável é:

```text
z =
 (b0*z0/w0 + b1*z1/w1 + b2*z2/w2)
 / iw
```

O fragment é rejeitado quando `z >= stored_depth`.

Menor vence; igual perde.

Essa é a expressão literal do código. Não deve ser descrita como necessariamente idêntica ao depth post-projection convencional de hardware sem teste específico.

## Lifetime do depth no proof renderer

`sh_soft_triangle` inicializa todo depth buffer recém-alocado com 1.0 e o libera ao terminar.

Chamadas separadas não compartilham depth e, portanto, não fazem occlusion entre si.

O helper serve para provar um triângulo e a pipeline de shader, não para montar uma scene multi-triangle.

Fragments descartados não atualizam color nem depth.

## Packing de cor no proof renderer

O helper multiplica RGBA por 255, arredonda e faz clamp explícito para 0..255 antes de montar o pixel 32-bit.

Assim, o helper de testes mantém comportamento determinístico mesmo se o shader produzir values fora do range normalizado.

O renderer software de produção do Gfx3D não faz exatamente a mesma coisa.

## Renderer software Gfx3D

O backend público usa `soft_tri` em `gfx3d.c`.

Ele usa os mesmos wrappers `sh_soft_vs` e `sh_soft_fs` e quase as mesmas equações de rasterização, mas escreve nos arrays persistentes do target.

Targets podem ter de 1×1 até 1920×1080.

Esse é o fallback real de Gfx3D em SOFTWARE ou quando AUTO perde VirGL.

## Lifecycle do target

`gfx3d_target_create` aloca array color 32-bit e depth float.

`alloc_target_cpu` não inicializa o conteúdo dessas allocations.

`gfx3d_clear` preenche color e configura cada depth cell para 1.0.

Resize libera os dois arrays e aloca storage novo também sem preservar ou inicializar os dados anteriores.

Por isso um target novo ou resized deve ser clearado antes de drawing determinístico.

## Clear

`gfx3d_clear` clampa RGBA negativos para zero, mas não faz clamp explícito de values acima de 1.0 antes do packing.

Ele sempre zera logicamente o depth para 1.0 em toda a surface.

Se o argumento `depth` for nonzero, a flag pública depth fica habilitada; zero não desabilita uma flag que já estava ativa.

Para desligar a flag pública é necessário `gfx3d_depth(ctx,0)`.

## Depth persistente do Gfx3D

`soft_tri` sempre compara:

```text
if (z >= target_depth) reject
```

e escreve o novo depth depois do fragment shader apenas se não houver discard.

Na revisão atual esse teste acontece mesmo com `depth_on` desligado.

A flag pública é usada no backend VirGL, mas não pelo raster software.

É uma incompatibilidade concreta entre backends.

## Culling e viewport

O context guarda cull flag e viewport dimensions.

`soft_tri` não consulta o cull state.

Também mapeia coordinates usando width/height completos do target, não o viewport salvo.

X/Y já são ignorados na API de viewport e, no software path, nem mesmo vp_w/vp_h são usados no coordinate mapping.

Essas diferenças precisam permanecer documentadas até serem corrigidas.

## W e clipping

No Gfx3D software, se qualquer W estiver aproximadamente entre ±1e-5, o triângulo inteiro é simplesmente skipped com sucesso.

O proof helper retorna erro com threshold um pouco maior.

Nenhum dos dois faz homogeneous clipping.

Triângulos atravessando near plane, far plane, side planes ou W=0 não seguem a mesma semântica de um clipper GPU completo.

Bounding-box clipping apenas protege writes fora do target.

## Packing de cor no path de produção

`soft_tri` multiplica outputs RGBA por 255 e faz packing diretamente.

Diferente de `sh_soft_triangle`, não há clamp explícito antes da conversão.

Shaders usados nesse path devem manter outputs no range [0,1] quando channels determinísticos forem necessários.

Essa diferença é concreta e merece cobertura de teste.

## Draw indexado e não indexado

`gfx3d_draw` suporta triplets de indices `uint16_t` ou groups consecutivos de três vertices.

Indices são verificados contra a quantidade de vertices antes do attribute load.

Cada triângulo segue para `soft_tri`.

Todos compartilham o mesmo depth persistente do target, ao contrário de chamadas isoladas do proof renderer.

## Complexidade

Uma execução do interpreter é O(número de CSIR instructions).

Cada triângulo executa três vertex shaders e um fragment shader por pixel aceito.

O raster é O(área da bounding box limitada).

A implementação atual recalcula edge denominator dentro do pixel loop e interpola sempre oito vec4 varyings por sample coberto.

Não existe SIMD por quads, JIT, tiling ou worker scheduling nesse path programável.

## Memória

`sh_exec_ir` usa arrays locais fixos.

`sh_soft_triangle` aloca um depth buffer W×H por chamada.

Gfx3D mantém color e depth persistentes por target.

Em Full HD, apenas os arrays CPU do target consomem aproximadamente 8,29 MB de color mais 8,29 MB de float depth, sem contar textures e mesh copies.

## Concorrência

O register file e control stacks do interpreter são locais à chamada.

Porém, arrays de uniforms de `ShProgram` e buffers de target Gfx3D são objetos mutáveis compartilhados sem locking geral.

Uniform update concorrente ou draws sobrepostos no mesmo target precisam de serialização externa.

O backend completo não deve ser considerado thread-safe apenas porque o interpreter usa estado local.

## Evidência de testes

`tools/test_shader.c` executa shaders software para constant output, MVP, texture sampling, diffuse lighting, IF/ELSE, loops unrolled, user functions, discard e sine.

O teste de triângulo 32×32 exige mais de 20 red pixels.

Também há checks de lighting para normal frontal e situação onde predomina ambient.

`tools/test_gfx3d_abi.c` inicia Gfx3D em SOFTWARE, cria target 32×32, clear, draw, readback e exige mais de dez red pixels.

Também testa vários resizes e ciclos repetidos de lifecycle de objects.

## Papel na validação cross-backend

Como CPU e VirGL nascem do mesmo CSIR verificado, o software path é uma referência semântica útil.

Ele não é um oracle bit-exact universal.

Existem diferenças conhecidas em transcendental approximations, sampling, depth-enable, culling, viewport e possivelmente representação de depth.

Differential tests precisam isolar essas diferenças e usar tolerâncias quando necessário.

## Limitações atuais

O interpreter é escalar e não possui JIT.

Sampling é nearest/clamp.

O proof renderer é limitado a 128×128 e recria depth a cada call.

O software renderer público não possui homogeneous clipping completo, culling funcional, viewport completo ou suporte real a depth disabled.

Não existem multisampling, stencil, blending, derivatives ou mipmapping.

O production color packing não clampa explicitamente fragment output.

Esses são limites concretos da revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Testes futuros recomendados

São úteis testes para RCP/RSQ com zero, tolerância software/VirGL de SIN/COS/POW, UVs fora de [0,1], discard preservando depth antigo, igualdade de depth, múltiplos triangles no mesmo target, depth disabled, culling, viewport, W=0/near-plane crossing e colors fora de [0,1].

Também deve existir teste explícito que defina se draw antes de clear em target novo é permitido ou proibido.

Um teste dedicado de depth deve comparar a fórmula software atual com VirGL e estabelecer a semântica desejada.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta o CSIR interpreter e os dois caminhos CPU programáveis de triângulo, mantendo-os separados do rasterizador legado `tri.c`.
