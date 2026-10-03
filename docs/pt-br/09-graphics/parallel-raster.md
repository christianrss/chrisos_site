---
id: parallel-raster
lang: pt-br
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/job.c
  - kernel/metal/job.h
  - kernel/gfx/tile.c
  - kernel/gfx/tile.h
  - kernel/gfx/tri_bin.c
  - kernel/gfx/tri_bin.h
  - kernel/gfx/scene.c
  - kernel/gfx/tri.c
  - kernel/gfx/zbuf.c
  - tools/job_host_stub.c
  - tools/job_host_stub.h
  - tools/test_tile.c
  - tools/test_tile_bin.c
  - tools/test_job_saturate.c
  - tools/test_scene.c
symbols:
  - job_submit
  - job_worker_once
  - job_worker_forever
  - job_wait_idle
  - tile_parallel_clear
  - tile_mesh_raster
  - tri_bin_reset
  - tri_bin_add
  - scene_draw
depends_on:
  - software-3d
  - kernel-jobs-kthreads
related:
  - triangle-rasterization
  - depth-buffer
  - virtio-gpu-virgl
---

# Rasterização software paralela

## Escopo

O ChrisOS paraleliza parte do trabalho gráfico usando a fila geral de jobs do kernel, e não um scheduler exclusivo do renderer.

Há dois padrões diferentes no source atual:

1. bandas ou tiles espacialmente disjuntos, em que cada worker possui pixels diferentes;
2. jobs triangle/tile, em que triângulos diferentes podem atingir o mesmo tile e os mesmos pixels.

Essa diferença determina se stores comuns no framebuffer e no z-buffer são suficientes ou se existe race.

A rasterização paralela atual é, portanto, um conjunto de estratégias de scheduling construídas sobre `job_submit`, clip rectangles e buffers de capacidade fixa.

## Base no job system

A fila fica em `kernel/metal/job.c`.

Cada job contém:

```text
JobFn fn
void *arg
```

e a função recebe também o índice da CPU que executa o trabalho.

A capacidade pública é:

```text
JOB_QUEUE_CAP = 1024
```

Head, tail e count da fila circular são protegidos por spinlock.

## Semântica de submission

`job_submit` rejeita function pointer null.

Com o lock adquirido, também falha quando o count já é 1024.

Submission bem-sucedida:

- grava function e argument;
- avança tail;
- incrementa count;
- incrementa atomicamente `g_inflight`;
- retorna 1.

Fila cheia retorna 0.

Esse retorno faz parte do contrato de correção. Ignorá-lo pode significar perder trabalho.

## Execução do worker

`job_worker_once(cpu)` primeiro coopera com polling/fencing de TLB.

Depois remove no máximo um job da fila sob spinlock.

O lock é liberado antes de executar a função.

Ao terminar, o worker incrementa `g_completed` e decrementa `g_inflight` atomicamente.

Rasterização demorada, portanto, não mantém o lock da fila durante o trabalho.

## Participação do BSP

`job_wait_idle` não é espera puramente passiva.

Enquanto `g_inflight` é diferente de zero, CPU 0 executa:

```text
job_worker_once(0)
```

e depois `pause`.

O bootstrap processor ajuda a drenar a fila em vez de depender apenas dos APs.

Quando a função retorna, todos os jobs que foram submetidos com sucesso terminaram.

Isso não significa que toda tentativa de submission tenha sido aceita.

## Loop dos APs

APs podem permanecer em `job_worker_forever`.

O loop atende TLB, habilita local APIC interrupts quando liberado, executa um job e usa `pause`.

Fencing de TLB pode desviar uma CPU do trabalho normal e levá-la ao estado halted.

Os workers gráficos compartilham, portanto, o mesmo mecanismo com outras responsabilidades do kernel.

## Evidência de saturação da fila

`tools/test_job_saturate.c` exercita diretamente a fila real.

Ele submete exatamente 1024 jobs e exige sucesso em todos.

A submission seguinte precisa falhar.

Depois de drenar a fila, uma nova submission precisa funcionar.

Isso fixa o comportamento bounded e a reutilização posterior da fila.

O kernel também possui `smp_job_selftest`, que usa ondas menores quando há múltiplas CPUs online.

## Tiles 64×64

`kernel/gfx/tile.h` define:

```text
TILE_SIZE = 64
```

O mesmo tamanho é usado por clear paralelo e tile binning.

Em 1920×1080 são 30 colunas por 17 linhas, totalizando 510 tiles para um clear de toda a surface.

Esse número é menor que a capacidade de 1024 da fila, desde que a fila comece livre.

## Clear paralelo

`tile_parallel_clear` calcula a grade necessária para cobrir o framebuffer.

Cada tile recebe um `TileClearArg` com destination pointer, dimensões, tile X/Y e color.

O worker limita os tiles da última coluna/linha ao tamanho real e chama `gfx_fast_fill_u32` em cada scanline.

Tiles diferentes não se sobrepõem.

É um particionamento naturalmente race-free do color buffer.

## Lifetime dos argumentos do clear

Os argumentos vivem em:

```text
static TileClearArg args[JOB_QUEUE_CAP]
```

A função avança um índice para cada tentativa de submission.

Antes de reutilizar o array ao atingir 1024 posições, chama `job_wait_idle` e volta o índice para zero.

Assim, jobs aceitos terminam antes do storage correspondente ser reutilizado.

Na resolução máxima atual, 510 tiles não atingem esse reuse barrier.

## Fragilidade na submission do clear

`tile_parallel_clear` chama `job_submit`, porém ignora o retorno.

Se a fila estiver vazia, um framebuffer máximo gera menos jobs que a capacidade.

Mas a fila é global e outros subsistemas podem já ocupar entradas.

Nesse caso, um job de clear pode ser rejeitado e a função ainda avança seu índice local.

Aquele tile deixa de ser limpo.

O código assume disponibilidade da fila sem tornar essa precondição explícita.

## Stub host de jobs

Os testes gráficos host usam `tools/job_host_stub.c`, baseado em pthreads.

Ele aceita de um a oito workers e cria threads durante `job_wait_idle`.

Sua fila interna possui:

```text
JOB_Q_CAP = 512
```

embora o header real declare 1024.

O workload atual de `test_tile` tem somente doze tiles, então essa diferença não interfere no teste.

O stub não deve ser interpretado como prova da capacidade real do kernel.

## Teste do clear paralelo

`tools/test_tile.c` usa 256×192 pixels.

Isso produz quatro colunas e três linhas de tiles: doze jobs.

O teste faz o mesmo clear magenta com um e dois workers host.

Confere primeiro e último pixel e compara checksum do framebuffer.

É evidência de determinismo para clear com tiles disjuntos naquele workload.

Não testa pressão de fila, jobs externos ou resolução máxima.

## Tile binning

`tile_mesh_raster` começa construindo um `TriBin`.

Para cada triângulo calcula min/max X/Y projetados e chama `tri_bin_add`.

O bin converte pixel coordinates para tiles com shift de seis bits, equivalente a 64 pixels.

Para cada tile sobreposto empacota:

```text
bits 31..16 : triangle ID
bits 15..8  : tile Y
bits 7..0   : tile X
```

## Capacidade do bin

`TRI_BIN_MAX = 4096`.

A capacidade mede overlaps triangle/tile, não quantidade de primitives de origem.

Um triângulo grande pode consumir muitas entries.

Quando `count` chega a 4096, overlaps seguintes simplesmente deixam de ser inseridos.

Não existe overflow flag retornada ao renderer.

Saturação do bin pode, portanto, remover trabalho visual.

## Dimensões guardadas no TriBin

`tri_bin_reset` salva `screen_w` e `screen_h`.

A implementação atual de `tri_bin_add` não usa esses campos para clamp.

Range check acontece depois, já em `tile_mesh_raster`, quando a entry foi empacotada e já consumiu capacidade do bin.

Bounds completamente ou parcialmente fora da tela podem gastar entries antes de serem descartados.

## Coordenadas negativas

Triângulos projetados podem ter X/Y negativos e ainda intersectar o framebuffer.

`tri_bin_add` aplica shift/packing às tile coordinates signed sem primeiro limitar a região para tiles válidos.

A fase posterior rejeita índices decodificados fora da grade, mas isso acontece tarde.

Além do desperdício de capacidade, o código não estabelece um contrato C portátil e robusto para packing de tile coordinates negativas.

O binning deveria clipar a bounding box antes da codificação.

## Argumentos triangle/tile

Para cada entry válida, `tile_mesh_raster` preenche:

```text
static TileTriArg args[TRI_BIN_MAX]
```

Cada estrutura contém framebuffer, clip rectangle do tile, três vertices projetados/depth e color.

O worker apenas chama `tri_fill_clip`.

Cada job usa uma posição distinta do array até o `job_wait_idle` final, evitando reuse prematuro dentro da chamada.

## Ownership entre tiles distintos

Um triângulo que toca vários tiles é submetido várias vezes.

Cada job recebe a geometria completa, porém um clip rectangle diferente.

`tri_fill_clip` intersecta a bounding box do triângulo com o tile.

Dois tiles distintos possuem regiões disjuntas.

O mesmo triângulo não escreve o mesmo pixel em dois jobs de tiles diferentes.

Esse particionamento espacial é seguro.

## Triângulos diferentes no mesmo tile

O problema aparece quando primitives distintas caem no mesmo tile.

Elas viram jobs separados com o mesmo clip rectangle.

Os triângulos podem atingir os mesmos pixels.

`zbuf_test` usa load/compare/store comum e a escrita de color ocorre depois em outra operação comum.

Não existe transação atômica depth+color.

Workers concorrentes podem, portanto, competir.

## Exemplo de race de depth/color

Considere dois fragments A e B no mesmo pixel.

Ambos podem ler o valor antigo FAR antes de qualquer store ficar visível.

Os dois concluem que passaram no depth.

Cada um grava seu depth e, depois, sua color.

Dependendo da interleaving, a cor final pode não corresponder ao menor depth final.

A semântica do z-buffer sequencial não é automaticamente preservada.

Essa é a principal limitação de correção do tile raster atual.

## Saturação em tile_mesh_raster

O bin aceita até 4096 entries, mas a fila possui 1024.

`tile_mesh_raster` não cria batches após 1024 attempts e não verifica o retorno de `job_submit`.

Workers podem drenar a fila enquanto submissions continuam; por isso vários workloads acima de 1024 entries podem funcionar.

Mas o sucesso passa a depender do timing.

Quando a fila fica cheia, jobs rejeitados desaparecem silenciosamente da imagem.

Não é apenas problema de performance.

## O barrier final não recupera jobs perdidos

Depois de percorrer o bin, a função chama `job_wait_idle`.

Isso espera todos os jobs aceitos, porque somente eles incrementam `g_inflight`.

Uma submission rejeitada nunca entra na contagem.

Logo, o barrier final não consegue detectar nem executar trabalho perdido.

Correção exige tratar o retorno no momento da submission.

## Estratégia da scene por bandas

`scene_draw` usa outro desenho.

O framebuffer é dividido em no máximo quatro bandas horizontais.

Se a altura é menor que quatro, usa apenas uma.

Cada `SceneBand` recebe um intervalo Y half-open exclusivo.

O worker percorre todos os nodes visíveis, mas cada `tri_fill_clip` só pode escrever dentro da sua banda.

## Ownership por banda

As bandas não se sobrepõem.

Um worker não escreve uma row de outra banda.

O z-buffer continua global, mas as células acessadas são diferentes porque o ownership de Y é exclusivo.

Isso permite usar operações não atômicas de color/depth sem competição entre bandas.

Existe trabalho redundante de setup dos nodes, porém o modelo de correção é mais claro.

## Fallback quando a fila da scene está cheia

A scene trata falha de submission explicitamente:

```text
if (!job_submit(band_job, &g_band[i]))
    band_job(&g_band[i], 0);
```

Se a fila está cheia, o BSP executa a banda de forma síncrona.

Nenhuma banda é perdida.

No final, `job_wait_idle` completa os jobs assíncronos aceitos.

É um padrão mais robusto que o usado em `tile_mesh_raster`.

## Lifetime de g_band

`g_band[4]` é estático.

`scene_draw` não retorna antes do barrier final.

Os argumentos continuam válidos durante toda a execução dos jobs.

Chamadas independentes simultâneas de `scene_draw`, porém, compartilhariam `g_band` e também estado global de visibilidade.

A API não é reentrante.

## Determinismo

Clear por tiles e scene por bandas podem ser determinísticos porque existe um único owner espacial por pixel.

Triangle/tile jobs não possuem essa propriedade quando primitives se sobrepõem dentro do tile.

Além disso, o z-buffer usa LESS estrito, então depth exatamente igual já depende de ordem mesmo sem race.

Correção paralela precisa distinguir política de igualdade, ownership espacial e ordem do scheduler.

## Trade-offs de performance

Parallel clear divide uma operação de bandwidth em blocos 64×64.

Scene bands distribuem screen work, mas cada banda repete o loop sobre nodes.

Triangle binning evita processar regiões não tocadas, porém expande um triângulo em vários jobs.

Para primitives pequenas, overhead de fila pode ser maior que o ganho.

Por isso o mesh legado só ativa tile raster em framebuffers maiores.

## Contenção com jobs não gráficos

A fila é compartilhada pelo kernel.

Kthreads e outros subsistemas também podem usar `job_submit`.

Código gráfico não pode presumir 1024 posições livres apenas porque possui menos de 1024 tarefas locais.

Essa propriedade torna ainda mais importante checar o retorno de submission.

Uma fila específica do renderer ou mecanismo de reserva tornaria a capacidade disponível mais explícita.

## Fronteira de segurança e lifetime

A fila não copia o argumento do job.

Ela guarda apenas o ponteiro.

A correção depende do objeto apontado continuar vivo até a execução terminar.

Os arrays estáticos e barriers finais satisfazem essa condição em chamadas sequenciais normais.

Reentrância, reuse prematuro ou stack arguments de curta duração poderiam quebrar o contrato.

## Lacunas de validação

Não existe teste host direto de `tile_mesh_raster` com triângulos sobrepostos e múltiplos workers.

Não existe teste de submissions gráficos com a fila parcialmente ocupada.

Também faltam testes de overflow do bin em 4096 entries e de bounds negativos/off-screen.

O checksum do clear não prova ausência de race em depth/color porque os jobs do clear não se sobrepõem.

## Correções recomendadas

A melhoria mínima é tratar todo retorno de `job_submit`.

Uma falha pode executar o job inline ou acionar drain-and-retry.

Uma arquitetura melhor agrupa todos os triângulos de um tile em um único job.

Esse worker processa sequencialmente depth/color dentro do tile, enquanto tiles diferentes continuam paralelos.

Assim, ownership de pixel fica explícito.

O bin também deveria clampiar ranges antes do packing e sinalizar saturação.

## Testes recomendados

Uma suite mais forte deve incluir:

- clear de frame inteiro com fila já ocupada;
- saturação do bin;
- bounding boxes negativas;
- muitos triângulos no mesmo tile;
- triangles near/far sobrepostos com vários workers;
- checksums repetidos de color e depth;
- falha forçada de submission e fallback;
- comparação entre output escalar e paralelo.

O objetivo deve ser equivalência de pixels para cenas em que o renderer sequencial possui resultado definido.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele separa os casos de partitioning disjunto, que possuem ownership claro, do caminho triangle/tile atual, em que saturação de fila e fragments concorrentes ainda são limitações explícitas de correção.
