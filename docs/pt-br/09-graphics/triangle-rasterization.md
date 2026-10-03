---
id: triangle-rasterization
lang: pt-br
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/tri.c
  - kernel/gfx/tri.h
  - kernel/gfx/zbuf.c
  - kernel/gfx/tile.c
  - kernel/gfx/tri_bin.c
  - kernel/gfx/mesh.c
  - kernel/gfx/voxel.c
  - tools/test_tri.c
  - tools/test_mesh.c
  - tools/test_chunk_mesh.c
  - tools/test_tile.c
  - tools/test_tile_bin.c
symbols:
  - edge
  - clip_box
  - tri_fill
  - tri_fill_clip
  - tri_fill_u32
  - tri_fill_lit
  - tri_fill_tex
  - tile_mesh_raster
  - tri_bin_add
depends_on:
  - clipping
related:
  - depth-buffer
  - textures
  - software-3d
  - parallel-raster
---

# Rasterização de triângulos

## Escopo

O ChrisOS rasteriza triângulos já projetados em `kernel/gfx/tri.c`. A entrada contém X/Y inteiros em screen space e depth inteiro; os caminhos texturizados também recebem UV e, em uma das variantes, normals.

Model transform, câmera, projeção e near-plane clipping acontecem antes. O rasterizador decide cobertura de pixels, interpola atributos, executa depth test e grava apenas fragments visíveis.

A implementação é deliberadamente pequena, permitindo acompanhar o hot path completo diretamente no source.

## Entradas públicas

`tri_fill` desenha um triângulo usando índice de paleta em todo o framebuffer.

`tri_fill_clip` adiciona um retângulo de restrição.

`tri_fill_u32` recebe RGB direto e funciona como núcleo de cor plana.

`tri_fill_lit` interpola UV e normals e pode usar textura.

`tri_fill_tex` interpola UV com um normal compartilhado pela face.

Todas convergem para o mesmo modelo de edge functions.

## Função de aresta

A cobertura usa:

```text
edge(A,B,P) =
    (Px-Ax)(By-Ay) -
    (Py-Ay)(Bx-Ax)
```

Os produtos são avaliados em `int64_t`, aumentando a margem contra overflow de intermediários em comparação com multiplicação apenas em 32 bits.

A área orientada do triângulo é calculada pela mesma função aplicada ao terceiro vértice.

## Triângulos degenerados

Área zero significa que os pontos projetados são colineares.

A função retorna imediatamente.

Não existe fallback para linha ou ponto.

O contrato de triangle fill exige área não nula em screen space.

## Normalização de winding

Se a área é negativa, os vértices 1 e 2 são trocados.

Depth, UV e normals associados acompanham a troca.

Depois a área é tornada positiva.

O loop interno pode então usar sempre:

```text
w0 >= 0 && w1 >= 0 && w2 >= 0
```

sem exigir orientação prévia do caller.

## Bounding box

A rotina calcula min/max X/Y dos três vértices e intersecta essa caixa com o clip rectangle e com os limites físicos do framebuffer.

Os endpoints superiores são exclusivos. `clip_x1` e `clip_y1` se tornam máximos válidos um pixel antes do endpoint.

Se a interseção for vazia, a função retorna antes dos loops.

Isso reduz custo e impede acesso fora da região permitida.

## Avaliação incremental

No início de cada scanline, os três edge weights são calculados para o primeiro X candidato.

Ao avançar um pixel em X, cada edge muda por um valor constante.

O source pré-calcula:

```text
col_step0 = y2 - y1
col_step1 = y0 - y2
col_step2 = y1 - y0
```

O inner loop usa somas em vez de multiplicações completas para cada sample.

Ao trocar de linha, os pesos iniciais são recalculados.

## Convenção da amostra

Coverage é testado em coordenadas inteiras `(x,y)`.

Não existe deslocamento de 0,5 para centro de pixel.

Essa convenção pode produzir bordas diferentes de renderizadores que usam half-pixel centers.

Comparações pixel-exact precisam considerar esse detalhe.

## Shared edges

As três edge functions são aceitas com `>= 0`.

Não existe uma top-left rule explícita que atribua uma aresta compartilhada somente a um dos triângulos adjacentes.

Dois triângulos coplanares podem, portanto, considerar a mesma amostra de borda coberta.

Como o z-buffer usa comparação estrita `z < stored`, a primeira escrita de depth igual normalmente permanece e a segunda falha.

O ownership da borda fica parcialmente dependente da ordem de draw.

## Caminho de cor plana

`tri_fill_u32` interpola depth:

```text
z = (w0*z0 + w1*z1 + w2*z2) / area
```

Se o valor interpolado fica negativo, é clampado para zero.

Somente um `zbuf_test` bem-sucedido permite a escrita do RGB.

Coverage por si só não altera o framebuffer.

`tri_fill_clip` converte índice de paleta por `gfx2d_color` e delega para esse caminho.

`tri_fill` delega novamente usando todo o framebuffer como região.

## Coeficientes baricêntricos

As variantes lit/textured convertem os pesos inteiros para floats:

```text
bw0 = w0 / area
bw1 = w1 / area
bw2 = w2 / area
```

Eles são usados para UV e normals.

Dentro do triângulo a soma fica aproximadamente em um, sujeita a conversão float.

## Interpolação afim

UV é interpolado diretamente com os pesos de screen space.

Isso é interpolação afim.

O rasterizador não carrega reciprocal W e não reconstrói U/V usando U/W, V/W e 1/W.

Triângulos com grande variação de profundidade podem apresentar distorção de textura em comparação com perspective-correct interpolation.

Normals em `tri_fill_lit` também são interpoladas de forma afim.

## Interpolação de depth

Depth usa os mesmos pesos de tela.

Os valores normalmente vêm do Z positivo de camera space escalado por 65536.

A abordagem é coerente com o renderer software atual, mas não reproduz o modelo de depth da pipeline homogênea de uma GPU moderna.

## tri_fill_lit

`tri_fill_lit` obtém base color da paleta ou usa cinza quando o índice é inválido.

U, V e os três componentes do normal são interpolados por fragmento.

Quando `texid >= 0`, `tex_sample` fornece a cor inicial. Caso contrário é usada a base color.

Depois cor e normal são enviados a `shade_phong`.

Não existe renormalização explícita da normal interpolada dentro da rotina antes dessa chamada.

## tri_fill_tex

O caminho orientado a voxel recebe UV por vértice, mas um normal único para todo o triângulo.

A iluminação é calculada uma única vez antes dos loops usando branco como base.

Depois cada texel amostrado é multiplicado pelos canais RGB da iluminação.

É mais barato que executar shading completo por pixel e combina com faces voxel de normal constante.

## Depth antes de textura

O z-test acontece antes de texture sampling e da modulação final.

Fragments ocultos por geometria mais próxima evitam trabalho de textura e lighting.

Isso funciona como early rejection no renderer software.

## Clip rectangles

Todas as funções de baixo nível recebem limites explícitos.

Além da proteção do framebuffer, esses limites permitem particionar trabalho.

Scene pode usar bandas horizontais. O tile renderer pode invocar a mesma primitiva uma vez por tile 64×64 tocado.

A edge equation não muda; muda somente a região onde a primitiva pode escrever.

## Tile rasterization

`tile_mesh_raster` calcula a screen-space bounding box de cada triângulo e chama `tri_bin_add`.

O bin cria uma entry para cada tile sobreposto.

O inteiro empacotado contém tri ID, tile Y e tile X.

Depois é submetido um job para cada combinação triangle/tile, chamando `tri_fill_clip` com os limites daquele tile.

É uma camada de scheduling ao redor do rasterizador escalar.

## Capacidade do bin

`TriBin` armazena no máximo 4096 entries.

Esse limite representa overlaps triangle/tile, não quantidade de triângulos.

Um triângulo grande pode consumir muitas posições.

Quando a capacidade termina, novas entries deixam de ser gravadas.

Não há expansão dinâmica nem relatório detalhado de overflow.

## Ownership paralelo

Triângulos diferentes que ocupam o mesmo tile produzem jobs distintos capazes de tocar os mesmos pixels.

Framebuffer stores e updates de z-buffer não são uma única transação atômica.

O clip rectangle, isoladamente, não garante determinismo quando o scheduler executa jobs concorrentes sobre a mesma região.

O capítulo de `parallel-raster` deve tratar essa propriedade em detalhe.

## Complexidade

Para uma bounding box clipada com A pixels candidatos, o loop custa O(A).

Área, winding e clipping da caixa são O(1).

Flat fill executa coverage, depth interpolation e z-test.

Textured/lit adicionam barycentrics float, UV, normal, sampling e shading.

Na prática, a área projetada e o modo de shading podem influenciar mais o custo que a contagem bruta de triângulos.

## Evidência executável

`tools/test_tri.c` exercita diretamente rasterização plana.

Ele exige que um triângulo vermelho pinte um pixel interno conhecido e mais de 80 pixels no total.

Depois desenha um triângulo verde mais próximo e verifica que ele substitui o vermelho na região comum.

Um triângulo maior também precisa cobrir mais de 400 pixels e várias colunas.

`tools/test_mesh.c` fornece uma primitiva pela memória CLVM e exige que `mesh_draw` altere pelo menos um pixel.

`tools/test_chunk_mesh.c` fornece integração mais alta com voxel/textura.

`tools/test_tile.c` compara clear paralelo com um e dois workers. `tools/test_tile_bin.c` verifica criação básica dos bins. Nenhum deles prova determinismo de triângulos concorrentes sobrepostos.

## Lacunas de validação

Ainda faltam testes diretos para ownership de shared edge, equivalência byte-exata de winding CW/CCW, todos os casos off-screen, valores UV conhecidos, normals interpoladas, overflow das 4096 entries e races entre jobs sobrepostos.

Golden images úteis deveriam incluir triângulos mínimos, quase degenerados, alinhados a bordas e pares adjacentes.

Property tests poderiam permutar a ordem dos vértices e comparar o resultado depois da normalização.

## Precisão e ranges

As edge functions usam 64 bits, mas coordenadas de entrada continuam sendo `int`.

O clip da bounding box protege o acesso ao framebuffer, porém não transforma valores inteiros extremos em geometria numericamente bem definida.

Projection e clipping anteriores continuam responsáveis por fornecer coordenadas razoáveis.

Depth interpolation combina weights de 64 bits e depth assinado de 32 bits. O range é adequado às resoluções e escalas atuais, mas não constitui aritmética geométrica arbitrariamente precisa.

## Continuidade após near clipping

O voxel renderer pode transformar um triângulo cruzando near plane em um quad e depois em dois triângulos.

Os novos vértices compartilham UV interpolado coerentemente.

Quando esses triângulos chegam a `tri_fill_tex`, porém, cada um é rasterizado independentemente.

Como não existe top-left rule explícita, ownership da diagonal compartilhada continua sujeito às regras de sample inteiro e depth igual.

Clipping correto e edge ownership são contratos diferentes.

## Relação com depth equality

A política de shared edges está acoplada à função de depth.

Se o z-test mudasse futuramente de LESS para LEQUAL, os pixels duplicados na aresta poderiam mudar de owner mesmo sem alterar `tri.c`.

Uma especificação formal futura deveria definir sample position, edge ownership e depth comparison em conjunto.

## Dependência de estado global

O color buffer é passado explicitamente para `tri_fill`, mas depth vem do módulo global de z-buffer atualmente bound.

Duas chamadas com color buffers diferentes não são automaticamente independentes se o depth target correto não for rebinderado.

Essa assimetria é importante: ownership da cor está no argumento, enquanto ownership de depth está implícito em estado global.

## Modos de no-draw

Ponteiro de pixels null, largura/altura não positivas, palette index inválido, área zero, clip box vazio ou depth rejeitado resultam em nenhuma escrita.

Como as funções são `void`, esses casos não retornam códigos detalhados de erro.

Diagnóstico precisa observar os inputs e o estado das etapas.

## Interpretação de performance

O bounding rectangle pode conter muitos pixels fora do triângulo.

Logo, O(A) mede área candidata e não área efetivamente coberta.

Triângulos muito finos e diagonais podem ter bounding boxes relativamente grandes e eficiência ruim.

Tiles e scissors reduzem regiões irrelevantes, mas ainda existe scan de bounding box dentro de cada região.

SIMD ou hierarquia de rejeição poderiam otimizar isso no futuro sem mudar a regra de cobertura.

## Determinismo como contrato

Para execução sequencial, a combinação de ordem de draw, regra de edge e LESS depth produz resultado reproduzível para os mesmos inputs.

Ao introduzir múltiplos workers, reproduzir o mesmo framebuffer exige que pixels concorrentes tenham uma ordem bem definida ou ownership exclusivo.

Assim, determinismo não é apenas propriedade matemática do triângulo; também depende do scheduler quando o tile path é usado.

Esse ponto deve ser medido com imagens/checksums repetidos em testes paralelos.

## Invariantes de debugging

Se nada é desenhado, primeiro confirme área não zero.

Depois verifique a bounding box clipada.

Se a caixa é válida, inspecione os sinais das edge functions.

Se coverage existe mas a cor não aparece, investigue depth.

Em geometria texturizada, fragmento visível com cor errada aponta mais para UV, texture ou lighting do que para coverage.

Essa decomposição evita confundir bugs de câmera/projeção com rasterização.

## Limitações atuais

O rasterizador usa posição de sample inteira, não possui top-left rule explícita, interpola atributos de forma afim e usa um modelo simples de depth em screen space.

É adequado para bring-up e experimentação gráfica no ChrisOS, mas não tenta reproduzir todas as regras de precisão e ownership de GPUs modernas.

## Nota de revisão

Este capítulo foi criado a partir da revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, usando o source e os testes host como evidência principal.
