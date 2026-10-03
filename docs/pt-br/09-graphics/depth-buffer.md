---
id: depth-buffer
lang: pt-br
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/zbuf.c
  - kernel/gfx/zbuf.h
  - kernel/gfx/gfx_fast.c
  - kernel/gfx/gfx_slot.c
  - kernel/gfx/tri.c
  - kernel/gfx/math3d.c
  - tools/test_zbuf.c
  - tools/test_tri.c
  - tools/test_mesh.c
symbols:
  - zbuf_bind
  - zbuf_set_size
  - zbuf_width
  - zbuf_height
  - zbuf_clear
  - zbuf_test
  - depth_to_z
depends_on:
  - triangle-rasterization
related:
  - software-3d
  - parallel-raster
  - gfx3d-api
---

# Depth buffer

## Escopo

O renderer software do ChrisOS armazena um depth unsigned de 32 bits para cada pixel.

A API de baixo nível é deliberadamente pequena: bindar storage, configurar dimensões, limpar a surface ativa e executar compare/update da célula.

A simplicidade ajuda no bring-up, mas o módulo é stateful e global. Correção depende tanto da matemática do depth quanto do lifecycle: qual buffer está bound, quais dimensões estão ativas e se houve clear no frame atual.

## Representação

Cada célula é `uint32_t`.

O sentinel usado para clear e distância máxima é:

```text
ZBUF_FAR = 0xFFFFFFFF
```

Valores menores são considerados mais próximos.

O z-buffer não armazena float.

O caminho software normalmente converte Z de camera space através de `depth_to_z`.

## depth_to_z

Para valores positivos comuns:

```text
depth = (uint32_t)(z * 65536)
```

Z menor ou igual a zero retorna `ZBUF_FAR`.

Z acima de 1.000.000 também retorna `ZBUF_FAR`.

É uma representação linear de distância positiva em camera space, não o depth normalizado de uma pipeline GPU convencional.

## Regra de comparação

`zbuf_test(x,y,z)` aceita somente quando:

```text
incoming < stored
```

Ao aceitar, substitui imediatamente a célula.

Ao rejeitar, mantém o valor anterior.

A depth function efetiva é LESS fixa.

## Igualdade

Depth igual falha.

Se uma célula contém 200 e outro fragmento chega com 200, o segundo retorna falso.

Isso cria comportamento first-writer para depths inteiros exatamente coplanares.

Também interage com shared edges: se dois triângulos cobrem a mesma amostra com depth idêntico, a primeira escrita normalmente permanece.

Não existe LEQUAL configurável, GREATER, ALWAYS ou depth bias nessa API.

## Bounds

O teste rejeita quando:

- não há depth buffer ativo;
- X é negativo;
- Y é negativo;
- X é maior ou igual à largura;
- Y é maior ou igual à altura.

A função falha antes de acessar memória fora da região.

O rasterizador já limita sua bounding box, mas o z-buffer mantém uma defesa final própria.

## Binding global

A implementação guarda:

```text
static uint32_t *g_zbuf
static int g_w
static int g_h
```

Existe apenas uma surface de depth ativa nessa camada.

`zbuf_bind(external)` muda o ponteiro. Passar null restaura o array estático.

Os triângulos recebem o color buffer explicitamente, mas obtêm depth via estado global. Essa assimetria é uma regra importante de ownership.

## Fallback estático

O array interno possui:

```text
1024 × 768
```

Com quatro bytes por célula, consome 3.145.728 bytes.

Os máximos públicos são maiores:

```text
ZBUF_MAX_W = 1920
ZBUF_MAX_H = 1080
```

Portanto o fallback não suporta todo tamanho aceito pela API.

## zbuf_set_size

A função normaliza as dimensões.

Width/height menores que 1 viram 1.

Width maior que 1920 é limitado a 1920.

Height maior que 1080 é limitado a 1080.

As dimensões normalizadas passam a representar o tamanho lógico ativo.

A capacidade do storage estático é verificada separadamente.

## Proteção contra overflow do fallback

Se o ponteiro ativo ainda é o array estático e as dimensões não cabem nele, `zbuf_set_size` faz:

```text
g_zbuf = 0
```

Assim o módulo desativa depth em vez de ultrapassar o array.

Sem buffer ativo, clear vira no-op e `zbuf_test` retorna falso.

É um modo de falha voltado à segurança de memória.

## Estado de recuperação

Depois de o ponteiro estático ser substituído por null devido a uma resolução grande, reduzir width/height não restaura automaticamente o array.

O caller precisa executar:

```text
zbuf_bind(0)
```

para selecionar o fallback novamente.

Dimensões lógicas e binding do storage são, portanto, estados independentes.

Esse comportamento merece teste próprio porque pode parecer contraintuitivo durante resize.

## Buffers externos

`zbuf_bind` recebe um ponteiro externo, mas não uma capacidade.

O caller precisa garantir que a alocação contenha pelo menos:

```text
g_w * g_h
```

células de 32 bits.

A camada não consegue descobrir o tamanho real do allocation.

Logo, segurança com external storage depende da coordenação correta entre allocator e dimensões.

## Graphics slots

`gfx_slot_alloc` é a camada de ownership para surfaces 3D.

Ela aloca color e depth arrays com:

```text
width * height * sizeof(uint32_t)
```

A API aceita até 1920×1080.

O novo depth buffer é inicializado por completo com `ZBUF_FAR`, depois as dimensões são configuradas e esse storage externo é bound.

Esse é o mecanismo normal para depth acima do limite 1024×768 do fallback estático.

## Falha parcial de alocação

Se color allocation funciona mas depth falha, color é liberado.

Se depth funciona mas color falha, depth é liberado.

O slot não é marcado como usado.

Assim, o caller não recebe metade de uma surface 3D.

O ownership só é publicado depois que os dois recursos existem.

## Resize 3D

`gfx_slot_resize` aloca novos color/depth buffers antes de liberar os anteriores.

O novo z-buffer é preenchido inteiro com `ZBUF_FAR`.

O conteúdo antigo de depth não é copiado.

Resize inicia uma surface de visibilidade nova, sem preservar occlusion anterior.

Se o tamanho não muda e depth já existe, os buffers podem ser reutilizados e rebound.

## Conversão para 2D

`gfx_slot_resize2d` pode transformar um slot em color-only.

Se havia z-buffer, ele é liberado e o ponteiro correspondente passa a null.

A existência de um graphics slot, portanto, não implica capacidade de depth.

Callers precisam saber em qual modo o slot foi criado.

## Free de slot

`gfx_slot_free` libera color e depth opcional.

Depois executa:

```text
zbuf_bind(0)
zbuf_set_size(320, 200)
```

O módulo de depth global volta ao fallback 320×200.

Como o binding é global, liberar um slot também altera o depth target visto por outros caminhos do renderer.

Em execução sequencial simples isso é aceitável; contexts concorrentes exigiriam isolamento adicional.

## Clear

`zbuf_clear` preenche todas as células ativas com `ZBUF_FAR`.

O trabalho é delegado a `gfx_fast_fill_u32`.

Se não há buffer ativo, não escreve nada.

O custo é O(W×H).

Em 1920×1080 são 2.073.600 células, cerca de 8,29 MB de writes.

## Lifecycle de frame

Um frame software coerente normalmente faz:

1. bind/select da surface de depth;
2. configuração das dimensões correspondentes;
3. clear;
4. rasterização;
5. `zbuf_test` para cada fragmento coberto.

Alguns caminhos como `mesh_draw` fazem clear explicitamente.

Se o clear é esquecido, depths do frame anterior podem ocultar geometria do frame atual.

## Compare/update combinado

`zbuf_test` não é consulta read-only.

Quando o fragmento vence, a célula é modificada imediatamente.

Não existe função separada de "peek".

Isso simplifica o hot path, mas uma ferramenta de diagnóstico que use `zbuf_test` pode alterar o estado que pretendia apenas observar.

## Ordem com color

Em `tri.c`, o depth compare/update ocorre antes da escrita de cor.

Nos caminhos texturizados, sampling e lighting também ficam depois do depth pass.

Isso evita trabalho de shading para fragments ocultos.

Em single-thread, a ordem é simples.

Em concorrência, porém, depth update e color write são operações distintas, não uma transação atômica.

## Risco de concorrência

`zbuf_test` usa load, comparação e store comuns.

Não existe lock por pixel nem compare-and-swap atômico.

Dois workers no mesmo pixel podem ler o mesmo depth anterior antes que qualquer update seja observado.

Ambos podem concluir que venceram e depois competir pelo depth e pela cor.

Particionamento espacial só resolve isso quando cada pixel possui ownership exclusivo ou há serialização dos fragments concorrentes.

## Precisão

Multiplicar por 65536 fornece resolução fracionária em relação às unidades inteiras de mundo/câmera.

Mesmo assim, a escala continua linear em camera-space Z.

Depth de GPU perspectiva costuma ter outra distribuição depois da transformação homogênea.

Em distâncias grandes, superfícies próximas podem quantizar para o mesmo valor inteiro e cair na regra first-writer da igualdade.

A representação atual é simples e adequada ao software renderer, mas não deve ser descrita como precisão equivalente à GPU.

## Comportamento de ZBUF_FAR

`ZBUF_FAR` é tanto o sentinel de clear quanto o retorno de `depth_to_z` para Z inválido, não positivo ou extremamente distante.

Como o teste usa LESS estrito, um incoming igual a `0xFFFFFFFF` nunca passa sobre uma célula recém-limpa.

Isso combina com o significado de "fora da faixa desenhável".

## Depth negativo interpolado

As funções de triângulo recebem depth por vértice em `int32_t`.

Se a interpolação produz valor negativo, `tri.c` clampa para zero antes de converter para unsigned.

Zero é o depth mais próximo possível e derrota qualquer valor positivo.

Geometria válida normalmente não deve depender dessa recuperação; clipping e projection anteriores devem manter os valores saneados.

## Clipping e depth são etapas diferentes

Near-plane clipping decide se uma primitiva é geometricamente válida antes da projeção.

Depth buffering decide qual fragmento válido vence quando vários chegam ao mesmo pixel.

Um triângulo pode falhar no near plane antes de existir qualquer depth test.

Dois triângulos válidos podem se sobrepor e depender exclusivamente do z-buffer.

As etapas são complementares, não substitutas.

## Propriedade de draw order

Para depths diferentes em execução sequencial, o resultado tende a ser independente da ordem.

Far seguido de near: near substitui.

Near seguido de far: far falha.

Para depth inteiro igual, a ordem importa porque igualdade falha.

Não existe polygon offset/depth bias nessa camada para separar superfícies coplanares.

## Custo de memória

Cada célula usa quatro bytes.

| Resolução | Células | Memória de depth |
|---|---:|---:|
| 320×200 | 64.000 | 256.000 bytes |
| 640×480 | 307.200 | 1.228.800 bytes |
| 1024×768 | 786.432 | 3.145.728 bytes |
| 1920×1080 | 2.073.600 | 8.294.400 bytes |

Um slot 3D também possui color buffer com quatro bytes por pixel, aproximadamente dobrando o consumo antes de texturas e demais recursos.

## Evidência executável

`tools/test_zbuf.c` fixa diretamente a comparação.

Depois do clear, depth 500 passa.

Depth 800 no mesmo pixel falha.

Depth 200 passa e substitui 500.

Um segundo 200 falha.

O teste também rejeita X negativo e Y igual à altura.

O segundo 200 confirma LESS estrito de forma explícita.

`tools/test_tri.c` fornece integração: um triângulo verde mais próximo substitui o vermelho mais distante em uma amostra conhecida.

`tools/test_mesh.c` mostra que o caminho de mesh usa a mesma infraestrutura com resultado visível.

## Lacunas de validação

Os testes diretos ainda não cobrem a desativação do fallback acima de 1024×768, recuperação por `zbuf_bind(0)`, external binding, external storage pequeno demais, clamp Full HD, efeitos de resize/free ou fragments concorrentes sobre a mesma célula.

Esses testes são importantes porque vários defeitos possíveis são de lifecycle e ownership, não de fórmula numérica.

## Complexidade

`zbuf_test` é O(1).

Binding, getters e mudança de size são O(1).

Clear é O(W×H).

Alocação, inicialização e resize de depth em gfx slot também são O(W×H).

Em superfícies grandes, bandwidth de clear/allocation pode custar mais que a comparação individual por fragmento.

## Invariantes de debugging

Se toda geometria 3D some depois de alterar resolução, verifique primeiro se existe buffer bound. Uma tentativa de usar o fallback acima de 1024×768 pode ter colocado `g_zbuf` em null.

Se o problema aparece depois do primeiro frame, confirme que clear ocorre a cada frame.

Se superfícies coplanares mudam conforme a ordem, lembre que equality falha.

Se corrupção aparece apenas com múltiplos workers, investigue ownership de pixel e race antes de alterar a fórmula de depth.

## Implicações de design da API

A API atual separa width/height e ponteiro global em chamadas distintas.

Uma futura surface de depth poderia encapsular pointer, capacity, dimensões e comparison mode no mesmo objeto.

Isso reduziria estados inconsistentes entre `zbuf_bind` e `zbuf_set_size`, além de facilitar contexts independentes.

Uma mudança assim deveria preservar a simplicidade dos testes atuais e tornar ownership explícito, não apenas renomear funções.

## Limitações atuais

O módulo possui um único binding global, comparison LESS fixa e não implementa stencil, MSAA depth, write mask configurável, depth bias ou update atômico para fragments concorrentes.

O fallback estático é menor que o máximo público e precisa de storage externo para resoluções maiores.

São limites da implementação atual do ChrisOS, não do conceito de depth buffering.

## Nota de revisão

Este capítulo foi criado a partir da revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, usando source e host tests como evidência principal.
