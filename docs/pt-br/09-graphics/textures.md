---
id: textures
lang: pt-br
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/tex.c
  - kernel/gfx/tex.h
  - kernel/gfx/tri.c
  - kernel/gfx/voxel.c
  - kernel/gfx/mesh.c
  - kernel/gfx/gfx3d_ctx.c
  - kernel/gfx/gfx3d_ctx.h
  - tools/test_chunk_mesh.c
  - tools/test_cube_mesh_f.c
symbols:
  - tex_init
  - tex_set_slot
  - tex_slot
  - tex_ofs
  - tex_sample
  - tex_state_save
  - tex_state_load
depends_on:
  - triangle-rasterization
related:
  - software-3d
  - shaders-csir
  - mine-graphics
---

# Texturas

## Escopo

O ChrisOS possui atualmente um subsistema de texturas software compacto, não um sistema geral de assets. A implementação em `kernel/gfx/tex.c` mantém um atlas procedural fixo com dezesseis slots, e cada slot contém uma textura RGB 16×16.

Não há decoder de PNG, DDS ou outro formato, nem upload genérico de imagem, objeto de asset vindo do filesystem ou resource manager de GPU nesse caminho.

A simplicidade permite testar o sampler e a rasterização antes de toda a infraestrutura de assets existir.

A contrapartida é direta: resolução, filtering e addressing são definidos em código e aplicações ainda não podem carregar imagens arbitrárias nesse módulo.

## Layout do atlas

O storage é `g_atlas[TEX_SLOTS][TEX_SIZE * TEX_SIZE]`, com `TEX_SLOTS = 16` e `TEX_SIZE = 16`.

Cada texel é um `uint32_t` com 24 bits RGB significativos em 0xRRGGBB. Um slot possui 256 texels, totalizando 1.024 bytes. O atlas completo ocupa 16.384 bytes.

O storage é estático; não existe uma alocação separada por textura.

## Inicialização lazy

`tex_init` constrói o atlas na primeira utilização. A flag `g_ready` impede reconstrução em chamadas seguintes.

Slots 0 a 7 possuem base colors e amplitudes de ruído explícitas. Os demais derivam parte da cor do próprio índice.

Todos passam por `fill_noise`. Nenhum arquivo precisa ser aberto.

## Gerador procedural

`fill_noise` usa uma sequência pseudoaleatória determinística. A seed inicial depende do slot:

```text
slot * 1103515245 + 12345
```

Cada texel avança `s = s * 1664525 + 1013904223`. Depois uma variação assinada limitada é somada aos canais-base.

O helper `rgb` clampa cada canal para 0..255. Assim, a mesma revisão do código sempre gera o mesmo atlas.

## Por que o determinismo importa

Texturas determinísticas facilitam regressões visuais. Uma mudança de framebuffer não pode ser atribuída a versão diferente de asset ou seed randômica.

Também permitem validar o renderer antes de filesystem, decoder e pipeline de conteúdo estarem maduros.

O custo é que a aparência dos materiais fica embutida no código. Não existe ainda um workflow de importação de imagens para esses slots.

## Concorrência na inicialização

O lazy init é protegido somente por um inteiro simples. Não existe lock em torno da primeira execução de `tex_init`.

No modelo de renderização controlado atual isso é suficiente, mas não constitui um protocolo thread-safe de first-use concorrente.

Uma evolução com workers deveria inicializar o atlas antes da concorrência ou usar semântica explícita de once.

## Estado global

O módulo mantém `g_slot`, `g_ofs_u`, `g_ofs_v` e `g_ready`.

`tex_set_slot` também garante a inicialização do atlas e clampa o argumento para 0..15.

Valor negativo vira 0. Valor >=16 vira 15.

`tex_slot` retorna o valor selecionado.

## Slot inválido no sampling

`tex_sample` usa uma política diferente da de `tex_set_slot`.

Se o `slot` explícito estiver fora de 0..15, o sampler troca o valor pelo slot global `g_slot`.

Ele não clampa o ID fornecido e não retorna erro.

Se o slot global for 3, por exemplo, `tex_sample(100,u,v)` amostra a textura 3.

Esse fallback influencia diretamente APIs que codificam material por número.

## Repeat de UV

U e V são normalizados para `0 <= coord < 1`.

Enquanto a coordenada é negativa, soma-se 1. Enquanto é >=1, subtrai-se 1.

Exemplos são 1.25 -> 0.25, -0.25 -> 0.75 e 2.0 -> 0.0.

A semântica é repeat. Não existe clamp-to-edge ou mirrored-repeat nesse sampler.

## Custo do wrap

O algoritmo usa loops repetidos. Para UV normal, o custo é pequeno.

Para um valor extremo como 100000, são necessárias muitas subtrações.

Isso significa que o sampler não tem custo estritamente constante para qualquer float fornecido.

Uma futura implementação baseada em remainder poderia evitar esse crescimento.

## Nearest-neighbor

Depois do wrap, `x = int(u * 16)` e `y = int(v * 16)`.

X e Y ainda são clampados para 0..15 como defesa final.

O lookup é `g_atlas[slot][y * 16 + x]`.

Não há bilinear filtering, mipmaps ou anisotropic filtering. O filtro é nearest-neighbor.

## Borda em 1.0

U ou V exatamente igual a 1 volta para zero antes da conversão.

Um valor imediatamente abaixo de 1 seleciona o último texel.

Essa seam é esperada no modo repeat e deve ser fixada em testes para evitar mudanças silenciosas de contrato.

## Offset do slot 5

`tex_ofs(du,dv)` grava offsets globais. Eles são somados somente quando a textura efetivamente amostrada é o slot 5.

Outros slots ignoram o offset.

O slot 5 pode, portanto, representar uma textura rolando sem alterar os UVs da geometria.

O offset é aplicado antes do wrap, permitindo atravessar a seam continuamente.

## Snapshot de TexState

`TexState` contém slot, offset U e offset V.

`tex_state_save` copia os globals e `tex_state_load` restaura os globals.

Ponteiro null é ignorado. O atlas não faz parte do snapshot porque seu conteúdo é global e determinístico.

## Integração com Gfx3DCtx

`Gfx3DCtx` armazena um `TexState` junto da view e do estado de iluminação.

As rotinas de contexto salvam e restauram os globals antigos.

Isso funciona como ponte entre uma implementação global legada e uma API superior que deseja estado por contexto.

Não torna acessos simultâneos automaticamente independentes; o contexto correto ainda precisa ser carregado antes do uso.

## IDs no voxel renderer

`voxel_set` clampa block ID para 0..15. Zero é ar e não produz face.

Blocks visíveis normalmente usam slots 1..15.

Cada face recebe UV (0,1), (1,1), (1,0), (0,0) e vira dois triângulos.

Quando near clipping cria uma interseção, U/V são interpolados junto da posição.

## Encoding em mesh_draw_f

`mesh_draw_f` reutiliza o argumento `color`.

Se `color < 16`, usa cor de paleta.

Se `color >= 16`, `texid = color - 16` e ativa o caminho texturizado.

Valores 16..31 correspondem naturalmente aos slots 0..15.

## IDs codificados fora da faixa

Um color acima de 31 produz `texid > 15`.

Esse ID chega a `tex_sample`.

Como ID explícito inválido cai para `g_slot`, o renderer não falha nem usa necessariamente slot 15.

Ele usa o slot global selecionado.

É um comportamento determinístico, mas potencialmente surpreendente, e deveria ser endurecido numa API futura.

## Limitação de UV no mesh

O ABI atual de mesh em memória CLVM contém posições e índices, não UV por vértice.

No modo texturizado float, todo triângulo recebe o mesmo layout (0,0), (1,0), (0,1).

Isso demonstra mapping, mas não representa um unwrap real vindo de um asset.

Um vertex format futuro precisa carregar atributos adicionais.

## Interpolação no rasterizador

`tri_fill_lit` e `tri_fill_tex` interpolam U/V por pesos baricêntricos de screen space.

É interpolação afim.

Não há reciprocal W nem reconstrução por U/W, V/W e 1/W.

Triângulos com grande variação de profundidade podem distorcer a textura.

O sampler apenas consome o U/V recebido; a limitação está na interpolação raster.

## Ordem depth/texture

O z-test acontece antes de `tex_sample`.

Fragments ocultos não fazem lookup de textura.

Isso reduz custo em overdraw.

Texture state determina a cor depois da visibilidade, não interfere na aprovação do depth.

## Relação com lighting

`tri_fill_tex` calcula iluminação de uma face uma vez e multiplica esse resultado nos texels.

`tri_fill_lit` interpola normals e chama `shade_phong` por fragmento visível.

A mesma textura pode, portanto, entrar em dois caminhos de lighting.

Não há normal map, roughness, metallic ou metadata de material associada ao slot.

## Sem alpha

Os texels possuem RGB.

O sampler não produz alpha e não define transparency testing.

A cor final vai diretamente ao framebuffer. Blending não pertence a esse módulo.

O byte alto do `uint32_t` não deve ser interpretado como um canal alpha com significado.

## Invariantes de transição de estado

Para material determinístico, o caller deve tornar o estado explícito antes do draw.

Uma sequência segura é carregar o contexto correto, configurar slot fallback quando necessário, aplicar offsets do slot 5 e só então rasterizar.

Salvar um contexto depois de outra rotina alterar `g_slot` captura esse novo valor.

Como IDs inválidos usam `g_slot`, um fallback aparentemente irrelevante pode se tornar visualmente observável.

## Modelo de erro da API

As funções não retornam erros na maior parte dos casos.

Slot selecionado inválido é clampado.

Slot de sampling inválido usa fallback.

UV fora da faixa é repetido.

Ponteiro null em save/load é ignorado.

Essa permissividade simplifica rendering normal, mas pode esconder bugs de upstream.

Uma build de debug poderia contabilizar IDs inválidos sem necessariamente mudar a política permissiva de release.

## Localidade de memória

Um slot possui apenas 1 KiB e o atlas inteiro ocupa 16 KiB.

Esse tamanho favorece cache locality.

Nearest sampling faz apenas um fetch de texel.

Quando o sistema adotar texturas maiores, mipmaps e assets externos, comportamento de cache será muito diferente da situação atual.

## Fronteira de segurança

O atlas atual não contém ponteiros fornecidos pela aplicação.

Depois da normalização de slot e coordenadas, o lookup acessa storage estático conhecido.

Isso mantém uma superfície pequena de risco.

Uma futura API de buffers de textura externos precisará validar capacidade, lifetime, ownership e permissões por contexto.

## Compatibilidade futura com assets externos

Adicionar image loading não deve alterar silenciosamente o significado dos slots existentes usados por voxel IDs e por `color - 16`.

Uma evolução segura precisa versionar ou tornar explícita a associação entre material ID e resource handle.

Também será necessário definir formato de pixel, stride, dimensões, addressing mode e ownership da memória.

Se esses atributos forem introduzidos apenas como globals adicionais, o mesmo problema de state leakage atual crescerá. Um objeto de textura por contexto é uma fronteira mais clara.

## Versionamento e reprodutibilidade

Hoje o atlas procedural é implicitamente versionado pelo próprio commit do código.

Qualquer mudança em seed, base color ou amplitude altera o resultado visual de todos os callers daquele slot.

Por isso regressões gráficas deveriam registrar a revisão do ChrisOS junto do framebuffer esperado.

Quando assets externos existirem, a revisão do código não será suficiente; hash ou versão do asset também deverá fazer parte da evidência reproduzível.

## Ownership e thread safety

Atlas, slot atual e offsets são globals.

Não há lock em torno das mutações.

Mudar `g_slot` enquanto outro worker amostra pode causar vazamento de estado entre contexts.

O modelo esperado é ownership explícito e serialização do estado.

Uma estrutura de sampler por contexto eliminaria essa dependência implícita.

## Complexidade

A inicialização grava exatamente 4.096 texels.

Sampling comum é O(1) para UV perto da faixa esperada.

Com UV extremo, o wrap passa a depender do número de períodos removidos.

O lookup nearest em si envolve poucas operações e um acesso ao array.

Na prática, quantidade de fragments rasterizados domina o custo do gerenciamento de textura.

## Evidência executável

A árvore inspecionada não contém `tools/test_tex.c` nem `tools/test_shade.c`.

`tools/test_chunk_mesh.c` fornece cobertura indireta importante.

Ele cria blocos de IDs diferentes, renderiza o mundo e exige mais de oito cores não nulas distintas.

Esse caminho atravessa `tri_fill_tex` e `tex_sample`.

É evidência de integração, mas não prova isoladamente wrap exato, fallback de ID inválido, animação do slot 5 ou todos os texels procedurais.

`tools/test_cube_mesh_f.c` valida o caminho float, porém atualmente usa palette color; não é teste direto de sampling.

## Testes recomendados

Um teste dedicado deve cobrir geração determinística, clamp em `tex_set_slot`, fallback em `tex_sample`, wrap negativo e >1, seam em U/V=1, offsets exclusivos do slot 5 e roundtrip de `TexState`.

Também deve testar UV extremamente grande para documentar a complexidade atual ou impor limite de entrada.

Um teste raster pode escolher texels conhecidos e tornar explícita a diferença entre interpolação afim e perspective-correct.

## Invariantes de debugging

Se vários meshes passam a usar a mesma textura, verifique o ID codificado e o valor de `g_slot`.

Se apenas um material se move com `tex_ofs`, confirme se é o slot 5.

Se a seam aparece em UV inteiro, lembre que o modo é repeat.

Se a distorção aumenta com profundidade, procure a interpolação afim, não a geração do atlas.

## Limitações atuais

Existem dezesseis texturas fixas 16×16, nearest-neighbor, repeat-only, sem mipmaps, alpha ou image loading.

Estado básico é global abaixo do save/load de contexto.

O mesh não carrega UV authored.

Essas escolhas mantêm o subsystem simples e previsível, mas ainda não compõem uma arquitetura de textura de produção.

## Nota de revisão

Este capítulo foi criado a partir da revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, com `tex.c`, seus consumidores e testes de integração como fonte principal.
