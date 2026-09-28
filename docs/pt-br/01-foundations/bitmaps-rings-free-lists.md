---
id: bitmaps-rings-free-lists
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pmm.h
  - kernel/metal/pmm.c
  - kernel/metal/job.h
  - kernel/metal/job.c
  - kernel/metal/klog.c
  - kernel/fs/cfs.c
  - kernel/fs/cfs.h
  - compiler/jit/jit.c
symbols:
  - pmm_bitmap
  - bitmap_is_used
  - bitmap_set_used
  - bitmap_set_free
  - pmm_alloc
  - pmm_alloc_contig
  - dma32_free
  - JOB_QUEUE_CAP
  - job_submit
  - job_worker_once
  - klog_putc
  - klog_copy
  - block_alloc
  - block_free
  - JitVa
  - jit_va_alloc
  - jit_va_free
depends_on:
  - arrays-lists-stacks-queues
  - algorithmic-complexity
related:
  - graphs-union-find
  - physical-memory
  - pmm-algorithms
  - kernel-jobs-kthreads
  - chrisfs
  - jit-memory
---

# Bitmaps, ring buffers e padrões de free list

<div class="abstract">
Bitmaps, circular buffers e free lists são estruturas compactas usadas em baixo nível quando allocation, bounded queues e reusable resources precisam ser representados sem grande overhead por objeto. A simplicidade aparente esconde invariantes centrais: o significado de cada bit, como scans terminam, como head/tail distinguem empty de full, se overwrite é permitido e se uma estrutura chamada informalmente de freelist é realmente uma lista ligada. Este capítulo desenvolve essas estruturas e as reconcilia com o source atual do ChrisOS. O physical memory manager usa um bit por página de 4 KiB sobre uma faixa rastreada de 32 GiB, com bit 1 significando used e bit 0 free; o subalocador DMA32 usa convenção oposta, em que bits setados significam free. ChrisFS usa allocation bitmap on-disk com alloc_hint. A fila de jobs do kernel é ring contado de 1024 entradas protegido por spinlock. O kernel log é overwrite ring de 8192 bytes que mantém os bytes mais recentes. O reuso de VA do JIT é uma tabela de 128 slots com used flag e reuso por tamanho exato; apesar de poder ser descrita operacionalmente como freelist, não é uma linked free list.
</div>

## Estruturas compactas em sistemas de baixo nível

Kernel e runtimes frequentemente precisam responder:

~~~text
resource i está livre ou usado?
qual é o próximo item da fila?
qual objeto liberado pode ser reutilizado?
~~~

Maps e containers genéricos poderiam responder, mas muitas vezes introduzem allocation e metadata desnecessários.

Bitmaps, rings e free-list patterns exploram restrições mais fortes:

- resources têm ids densos;
- capacity é fixa ou limitada;
- FIFO é necessária;
- estado de reuso cabe em bit ou index.

O ganho é previsibilidade, desde que os invariants estejam explícitos.

## Bitmaps

Bitmap associa um bit a cada logical element.

Para index i:

~~~text
byte = i / 8
bit  = i % 8
mask = 1 << bit
~~~

Teste:

~~~text
(bitmap[byte] & mask) != 0
~~~

Set:

~~~text
bitmap[byte] |= mask
~~~

Clear:

~~~text
bitmap[byte] &= ~mask
~~~

A aritmética é simples. O ponto crítico é definir o que 0 e 1 significam.

## Semântica do bit faz parte do contrato

Duas convenções igualmente válidas:

~~~text
1 = allocated
0 = free
~~~

ou:

~~~text
1 = free
0 = allocated
~~~

Misturar as duas produz corrupção.

O significado precisa ser local e explícito, especialmente quando o mesmo subsystem contém mais de um bitmap.

ChrisOS atual demonstra as duas convenções no PMM.

## Representação do PMM

O PMM define:

~~~text
PMM_PAGE     = 4096 bytes
PMM_MAX_PHYS = 32 GiB
~~~

Logo:

~~~text
32 GiB / 4 KiB = 8.388.608 páginas
~~~

Com um bit por página:

~~~text
8.388.608 / 8 = 1.048.576 bytes
~~~

pmm_bitmap ocupa 1 MiB.

A convenção é:

~~~text
bit 1 = página usada/reservada
bit 0 = página livre
~~~

bitmap_is_used, bitmap_set_used e bitmap_set_free implementam diretamente esse mapping.

## Inicialização conservadora do PMM

pmm_init começa preenchendo todo bitmap com 0xff:

~~~text
todas as páginas rastreadas = used
~~~

Em seguida lê o Limine memory map e limpa bits apenas das regiões classificadas como usable.

Depois re-reserva áreas que não podem ser alocadas, inclusive low memory e ranges não utilizáveis.

Sequência:

~~~text
inicia indisponível
prova que a região é usable
marca free
reaplica reservas necessárias
~~~

Esse modelo é conservador: informação incompleta tende a reter memória, não a distribuir um frame desconhecido.

## Scan de allocation no PMM

pmm_alloc procura uma página free começando em pmm_cursor.

Se não achar após o cursor, tenta novamente desde physical zero.

O scan pode pular um bitmap byte completo quando:

~~~text
page está alinhada ao início do byte
e
pmm_bitmap[byte] == 0xFF
~~~

porque as oito páginas representadas estão used.

Essa otimização reduz verificações sem alterar o resultado.

O worst case ainda é linear na faixa examinada.

## Cursor e hints

Sem hint, allocations repetidas podem rescanner o mesmo prefixo ocupado.

pmm_cursor move o início da procura para perto da fronteira recente.

Ao liberar:

~~~text
if freed_phys < pmm_cursor:
    pmm_cursor = freed_phys
~~~

o allocator volta a considerar espaço anterior.

Hint não é source of truth.

Mesmo se estiver subótimo, correctness deve vir do bitmap; o hint só muda ordem e performance.

## Allocation contígua

pmm_alloc_contig precisa encontrar count páginas consecutivas free.

Bitmap representa state compactamente, mas não oferece por si só um índice logarithmic de runs.

O PMM atual enumera free runs e também pode fazer scan por um run solicitado.

Worst-case continua proporcional ao espaço pesquisado.

Se contiguous allocation se tornasse dominante, alternativas possíveis seriam buddy metadata, free-run trees, segregated run lists ou hierarchical bitmaps.

Essas alternativas não são claims do source atual.

## DMA32 usa convenção oposta

O PMM reserva um pequeno range DMA32 para UHCI.

O estado vive em:

~~~text
uint32_t dma32_free
~~~

Aqui:

~~~text
bit 1 = free
bit 0 = allocated
~~~

Allocation cria mask:

~~~text
need = (1 << pages) - 1
mask = need << i
~~~

e aceita um range quando:

~~~text
(dma32_free & mask) == mask
~~~

Depois limpa os bits.

Free volta a setá-los.

A convenção inversa é correta porque a state machine é separada, mas mostra por que nunca se deve inferir a semântica de um bit apenas pelo nome bitmap.

## Complexidade de bitmap

Consultar um bit conhecido é O(1).

Encontrar um free resource não é automaticamente O(1).

Linear scan de n bits tem worst case:

~~~text
O(n)
~~~

Word-at-a-time reduz constantes ao testar 32 ou 64 bits juntos.

Instruções como count-trailing-zeros localizam rapidamente um bit dentro de word não-zero.

Hierarchical bitmap adiciona summary levels para achar words candidatas mais rapidamente.

Representation e search algorithm são escolhas separadas.

## Bitmap de allocation do ChrisFS

ChrisFS usa bitmap para data blocks.

bitmap_get e bitmap_set transformam data-block index em:

- bitmap sector LBA;
- byte no sector;
- bit no byte.

Convenção:

~~~text
1 = block used
0 = block free
~~~

block_alloc começa em:

~~~text
fs->alloc_hint
~~~

e faz wrap pela população de data blocks.

Ao claimar um block:

1. seta o bit;
2. zera o block;
3. avança alloc_hint;
4. retorna o LBA.

block_free pode mover alloc_hint para trás quando um block anterior se torna free.

Esse hint substituiu o comportamento anterior de recomeçar sempre do zero.

## Failure atomicity no ChrisFS

Allocation muda mais de um estado.

Sequência conceitual:

1. encontra free bit;
2. seta bitmap;
3. inicializa block zerado;
4. entrega ownership.

Se a escrita do block falhar depois de setar o bitmap, o código tenta:

~~~text
bitmap_set(index, 0)
~~~

para rollback.

Isso evita transformar falha de initialization em leak permanente de allocation state.

Crash consistency completa pertence aos capítulos de ChrisFS e journaling.

## Ring buffers

Ring buffer mantém sequência lógica em array físico fixo e faz wrap nos índices.

Com capacity C:

~~~text
next(i) = (i + 1) mod C
~~~

O fim físico do array não é o fim lógico da queue.

Push/pop podem ser O(1) sem deslocar elementos.

## Ambiguidade empty/full

Se ring guarda apenas head e tail:

~~~text
head == tail
~~~

pode representar empty ou full após wrap.

Soluções comuns:

1. count explícito;
2. reservar um slot;
3. full flag separada;
4. sequence counters monotônicos.

Cada solução muda usable capacity.

Ring com slot reservado comporta C - 1 elementos.

Ring com count pode usar todos os C slots.

## Job queue do ChrisOS: counted FIFO ring

O job subsystem define:

~~~text
JOB_QUEUE_CAP = 1024
~~~

e mantém:

~~~text
g_queue[JOB_QUEUE_CAP]
g_q_head
g_q_tail
g_q_count
~~~

job_init zera head, tail e count.

Submission detecta full por:

~~~text
g_q_count == JOB_QUEUE_CAP
~~~

Logo os 1024 slots são utilizáveis.

## Invariante de submission

Sob g_q_lock, job_submit:

1. grava fn e arg em g_q_tail;
2. tail = (tail + 1) mod capacity;
3. incrementa count;
4. incrementa inflight;
5. libera lock.

Invariante:

~~~text
0 <= g_q_count <= JOB_QUEUE_CAP
~~~

Full é count == 1024.

Empty é count == 0.

head pode ser igual a tail nos dois casos; count remove a ambiguidade.

## Remoção de job

job_worker_once adquire o mesmo lock.

Se count > 0:

1. copia g_queue[g_q_head] para variável local;
2. avança head;
3. decrementa count;
4. libera lock.

A callback só roda depois do unlock.

Isso limita critical section e evita executar arbitrary work segurando queue lock.

## Concorrência do ring de jobs

A queue atual não é lock-free.

Correctness depende de g_q_lock serializar head, tail, count e slot publication.

g_completed e g_inflight são atualizados atomicamente por outro mecanismo.

Tornar apenas head/tail atomic não criaria automaticamente um MPMC ring correto.

Uma queue lock-free precisaria de protocol adicional por slot ou sequence numbers.

## Saturation

job_submit retorna zero quando full.

Não há overwrite de jobs antigos.

Caller que precisa eventual submission deve aplicar retry/backpressure.

O self-test do subsystem faz exatamente isso: ajuda a consumir jobs e tenta novamente.

Bounded queue saturation é parte da policy.

## Klog: overwrite ring

klog define:

~~~text
KLOG_CAP = 8192
g_log[KLOG_CAP]
g_pos
g_len
~~~

Cada char novo vai para g_pos.

g_pos avança e volta a zero ao chegar no capacity.

g_len cresce até KLOG_CAP e depois satura.

Quando full, writes seguintes substituem os bytes mais antigos.

Isso atende bem um diagnostic tail que prioriza eventos recentes.

## Reconstrução de ordem lógica no klog

Para copiar os n bytes mais recentes:

~~~text
start = (g_pos + KLOG_CAP - n) % KLOG_CAP
~~~

e cada byte é lido de:

~~~text
g_log[(start + i) % KLOG_CAP]
~~~

Isso devolve chronological order mesmo se a região física estiver dividida entre o fim e o início do array.

Mutation e copy são protegidos por spinlock.

## Job ring versus klog ring

| Propriedade | Job queue | klog |
|---|---|---|
| payload | Job | byte |
| capacity | 1024 | 8192 |
| full policy | rejeita | overwrite oldest |
| empty/full state | count | len + write position |
| consumer | workers | copy/read tail |
| synchronization | spinlock | spinlock |

Dizer apenas que ambas são rings não captura failure policy.

## Free lists

Classic free list mantém reusable objects em chain:

~~~text
free_head -> object -> object -> object
~~~

Free object guarda next-free.

Allocation remove do list; release insere novamente.

Push/pop no head são O(1).

O custo é metadata e pointer integrity.

## Intrusive free list

Em intrusive design o próprio slot armazena next_free enquanto não está live.

Exemplo:

~~~text
struct Slot {
    union {
        LivePayload live;
        uint32_t next_free;
    };
}
~~~

Quando live, o payload vale.

Quando free, os mesmos bytes viram metadata de link.

Isso evita node allocation separado, mas exige state transition rigorosa.

## Free lists ordenadas e segregadas

Address-ordered free list ajuda coalescing de neighbors.

Size-segregated free lists agrupam blocks por size class e reduzem search.

O melhor design depende de fragmentation, latency e implementação.

O kernel heap atual não é classificado aqui como linked free-list allocator porque o source revisado faz sequential scan de heap blocks dentro de arenas e marca used/free sem manter free_head/next-free chain explícita.

## Estrutura de reuso de VA do JIT

O JIT define:

~~~text
JIT_VA_SLOTS = 128

struct JitVa {
    uint64_t virt;
    uint32_t pages;
    int used;
}
~~~

jit_va_alloc procura linearmente entry com:

~~~text
virt != 0
used == 0
pages == requested_pages
~~~

e reutiliza o range.

jit_va_free procura virt correspondente e limpa used.

Operacionalmente isso é uma pool de ranges liberados.

Estruturalmente não é linked free list.

Não há free_head nem next_free.

## Reuso apenas de mesmo tamanho

JIT só reutiliza slot se:

~~~text
stored_pages == requested_pages
~~~

Range de quatro páginas não é dividido para pedido de duas páginas.

Ranges adjacentes não são coalesced.

Vantagens:

- implementation simples;
- reuse determinístico;
- menos metadata.

Limitações:

- virtual-address fragmentation;
- O(128) scan;
- sem best-fit;
- sem split/merge.

## Bump frontier mais reusable slots

Se não houver free record de mesmo tamanho, jit_va_alloc usa:

~~~text
g_jit_virt_next
~~~

desde que o range fique abaixo de JIT_VIRT_LIMIT.

Depois grava metadata no primeiro slot nunca usado, identificado por virt == 0.

O design combina:

- monotonic bump para VA nova;
- metadata table fixa;
- exact-size reuse.

Não é general extent allocator.

## Falhas de free list e slot tables

Linked free list pode falhar por:

- cycle;
- duplicate insertion;
- dangling link;
- live object na free list;
- ABA em lock-free stack.

Reusable-slot table falha de formas diferentes:

- duplicate live ranges;
- used flag incoerente;
- metadata slots esgotados;
- mesmo VA devolvido duas vezes;
- wrong-size reuse.

A classificação correta determina o que testar.

## Comparação de complexidade

| Estrutura | Operação com posição conhecida | Search/allocation worst case |
|---|---:|---:|
| bitmap conhecido | O(1) | — |
| bitmap linear | — | O(n bits) |
| counted ring | O(1) | O(1) |
| overwrite ring | O(1) | O(1) |
| linked free-list head | O(1) | O(1) |
| JIT slot table | update O(1) após localizar | O(128) |
| ChrisFS bitmap alloc | bit update O(1) após localizar | O(data blocks) |
| PMM contiguous search | mark O(k) | scan linear de runs |

Big-O precisa incluir localização e mutation.

## Cache e locality

Bitmaps são densos: uma cache line representa muitos resources.

Rings mantêm arrays contíguos e boa locality.

Linked free lists podem espalhar nodes e causar pointer-chasing misses.

Slot tables indexadas trocam metadata fixa por melhor locality.

Essa densidade explica por que kernels favorecem bitmaps e rings quando ids são densos.

## Synchronization e ownership

Nos exemplos atuais:

- PMM bitmap: IRQ-safe recursive same-CPU PMM lock;
- job ring: spinlock;
- klog ring: spinlock;
- ChrisFS bitmap: filesystem locking model;
- JIT VA slots: ownership ligado ao JIT/MM lifecycle, sem claim de lock-free allocator.

Uma operação OR/AND ser machine-sized não torna allocation inteira atomic.

Allocation envolve observar state, claimar recurso, atualizar counters e publicar ownership.

## Segurança

Metadata compacta controla muitos recursos.

Um bit corrompido pode causar double allocation de physical page.

Count corrompido pode produzir out-of-bounds ring access.

Duplicate free-list entry pode entregar o mesmo objeto a owners diferentes.

Defesas:

- range checks;
- capacity checks;
- consistency counters;
- poison/debug state;
- double-free detection;
- lock rules;
- saturation policy;
- wraparound/full tests.

Quanto menor a metadata, maior o impacto potencial de cada bit.

## Modelo de validação

O checker determinístico valida:

- bitmap set/clear/test;
- convenções opostas de used/free;
- first-fit com moving hint;
- contiguous run allocation;
- counted-ring FIFO com wrap;
- full rejection usando todos os slots;
- overwrite ring retendo os bytes mais novos;
- chronological copy após wrap;
- linked free-list model;
- JIT equal-size reusable slots;
- anchors de PMM bitmap, DMA32, ChrisFS bitmap/alloc_hint, job ring, klog ring e JIT slot table.

Esses checks validam representation e source contract, não substituem PMM SMP stress, crash testing do filesystem nem testes de JIT/TLB lifecycle.

## Fronteira do ChrisOS atual

Na revisão da3df29cb397932c43d32373871fb9380e688ade o source estabelece:

- bitmap PMM de um bit por physical page;
- DMA32 free mask de 32 bits com semântica inversa;
- bitmap on-disk de data blocks do ChrisFS com alloc_hint;
- counted FIFO ring de 1024 jobs;
- overwrite klog ring de 8192 bytes;
- JIT VA reuse table de 128 entries com exact-size matching.

Não há uma biblioteca genérica que implemente todas as variantes descritas.

A tabela JIT não deve ser reclassificada como pointer-linked free list.

## Proveniência da revisão

As afirmações de implementação foram conciliadas com ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Source revisado:

- kernel/metal/pmm.h;
- kernel/metal/pmm.c;
- kernel/metal/job.h;
- kernel/metal/job.c;
- kernel/metal/klog.c;
- kernel/fs/cfs.h;
- kernel/fs/cfs.c;
- compiler/jit/jit.c.

O capítulo distingue os nomes das famílias de suas representations concretas: bit meaning é local, rings podem rejeitar ou sobrescrever, e reusable-slot table não é automaticamente linked free list.
