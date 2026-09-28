---
id: heap-ownership
lang: pt-br
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/heap.c
  - kernel/metal/heap.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/spin.c
  - kernel/metal/spin.h
  - kernel/metal/kthread.c
  - kernel/metal/job.c
  - tools/test_pmm_heap_smp.c
symbols:
  - heap_init
  - heap_grow
  - heap_claim_run
  - add_arena_phys
  - kmalloc
  - kmalloc_in_arenas
  - kfree
  - coalesce_forward
  - heap_used_bytes
  - heap_free_bytes
  - heap_arena_count
  - heap_selftest
depends_on:
  - physical-memory
  - pmm-algorithms
  - hhdm
related:
  - spinlocks
  - resource-lifetime
  - tlb-shootdown
  - kernel-jobs-kthreads
---

# Heap do kernel, ownership e ciclo de vida das alocações

## Escopo

PMM e heap resolvem problemas de alocação diferentes.

O PMM possui e distribui páginas físicas. Sua unidade natural é 4096 bytes, e ele trabalha com endereços físicos, contabilização de páginas livres e runs contíguos.

Subsistemas do kernel precisam frequentemente de objetos muito menores que uma página: descritores, strings, buffers gráficos, memória temporária de compiladores, work buffers de filesystem, estado de transferência de rede e stacks privadas de kthreads.

O ChrisOS posiciona um heap acima do PMM. O heap reivindica runs físicos contíguos, acessa-os pelo higher-half direct map, subdivide-os em blocos de tamanho variável e serializa seus metadados por meio de um spinlock global.

A implementação atual é deliberadamente simples:

- alinhamento de payload em 16 bytes;
- header de 16 bytes por bloco;
- busca first-fit;
- split de blocos livres suficientemente grandes;
- coalescing somente para frente;
- até 32 arenas;
- crescimento usando runs físicos contíguos do PMM;
- tamanho mínimo de arena de 16 páginas;
- reserva física de 32 MiB preservada fora do crescimento oportunista do heap.

![Ciclo de alocação do heap do ChrisOS](../../assets/diagrams/heap-ownership-pt-br.svg)

O heap também estabelece uma fronteira de ownership. Depois que páginas do PMM são reivindicadas como arena, o PMM não pode alocá-las novamente enquanto pertencem ao heap. Na revisão atual, arenas do heap não são devolvidas ao PMM durante operação normal.

## Layout dos metadados

Cada bloco começa com:

~~~c
struct heap_block {
    uint64_t size;
    uint32_t used;
    uint32_t pad;
};
~~~

A estrutura ocupa 16 bytes, exatamente HEAP_USER_OFF.

O ponteiro entregue ao chamador é:

~~~text
endereço do header + 16 bytes
~~~

e o próximo bloco é calculado por:

~~~text
próximo = header atual
        + 16 bytes de metadata
        + tamanho do payload atual
~~~

O campo size representa somente o payload, não o header.

Assim o allocator forma uma lista implícita: não existem ponteiros next/prev nos blocos. A posição seguinte é derivada aritmeticamente.

## Alinhamento

HEAP_ALIGN vale 16 bytes.

kmalloc arredonda todo pedido não-zero:

~~~text
need = align_up(size, 16)
~~~

A base de cada arena também precisa ser alinhada a 16 bytes.

Como o header ocupa exatamente 16 bytes, user_from_block mantém alinhamento de 16 bytes para todo payload construído corretamente.

Isso atende requisitos comuns de ABI x86-64 para objetos comuns e vários usos SIMD, embora não exista API para alinhamentos maiores que 16 bytes.

kmalloc(0) retorna null.

## Arenas

O heap mantém array fixo:

~~~text
HEAP_ARENA_MAX = 32
~~~

Cada heap_arena contém:

- base: endereço virtual HHDM da arena;
- limit: tamanho total em bytes.

O backing físico de cada arena é contíguo porque heap_grow chama pmm_alloc_contig.

Arenas distintas não precisam ser adjacentes entre si.

Toda arena nasce como um único bloco livre:

~~~text
header na base
payload = bytes da arena - 16
used = 0
~~~

Depois pode ser subdividida sucessivamente.

## Relação com HHDM

PMM retorna endereço físico.

Código C do kernel não deve assumir que esse endereço pode ser dereferenciado diretamente.

add_arena_phys converte a base física com bootinfo_phys_to_virt.

A partir daí o heap trabalha com endereço virtual do direct map.

Fluxo:

~~~text
run físico do PMM
      |
      v
bootinfo_phys_to_virt
      |
      v
endereço virtual HHDM
      |
      v
metadata + payloads do heap
~~~

Por isso o heap depende do contrato do higher-half direct map.

## Inicialização

heap_init ocorre antes do uso concorrente normal.

A sequência é:

1. inicializar heap_lock;
2. zerar narenas;
3. marcar heap_ready = 0;
4. verificar se o PMM possui mais memória que a reserva;
5. percorrer runs livres com pmm_foreach_free_run;
6. reivindicar runs adequados por heap_claim_run;
7. usar heap_grow se nenhuma arena foi obtida;
8. marcar heap_ready = 1;
9. calcular e registrar used/free.

A inicialização tenta aproveitar múltiplos runs físicos disponíveis em vez de depender de um único heap estático.

## Reserva física

PMM_KEEP vale:

~~~text
32 MiB
~~~

O heap converte isso para páginas com keep_pages.

heap_claim_run e heap_grow recusam consumo que ultrapasse essa reserva.

A intenção é evitar que o heap geral absorva todas as páginas livres, preservando capacidade para:

- page tables;
- frames de processo;
- buffers de dispositivos;
- alocações físicas diretas;
- outras estruturas que não pertencem ao heap.

Essa reserva é política baseada na contagem de páginas livres, não uma região física fixa separada.

## Reivindicação inicial dos runs

pmm_foreach_free_run chama heap_claim_run para cada run livre utilizável.

heap_claim_run limita quanto pode consumir mantendo PMM_KEEP.

Se o resultado tiver menos que HEAP_MIN_ARENA_PAGES, o run é ignorado.

HEAP_MIN_ARENA_PAGES é:

~~~text
16 páginas = 64 KiB
~~~

Quando o run é adequado, o callback chama pmm_claim_at para registrá-lo como usado no PMM e depois add_arena_phys para convertê-lo em arena.

Se o registro da arena falha depois do claim, pmm_free_contig devolve as páginas.

Esse é um caminho concreto de rollback após falha parcial.

## Recursão do PMM durante heap_init

Existe uma interação sutil.

pmm_foreach_free_run mantém pmm_lock enquanto chama o callback.

heap_claim_run pode chamar pmm_claim_at, que entra novamente no PMM na mesma CPU.

Um spinlock não-recursivo comum deadlockaria.

O PMM implementa recursão controlada por CPU:

1. entrada externa salva IF e executa CLI;
2. adquire pmm_lock;
3. define pmm_depth[cpu] = 1;
4. entrada aninhada na mesma CPU apenas incrementa depth;
5. somente a saída externa libera o lock e restaura IF.

Esse mecanismo existe para nesting controlado do PMM. Não transforma todos os spinlocks do kernel em locks recursivos.

## Crescimento após inicialização

kmalloc primeiro busca nas arenas existentes.

Se não encontrar bloco, chama heap_grow ainda segurando heap_lock.

heap_grow calcula páginas suficientes para:

~~~text
payload requerido + um header
~~~

e eleva o pedido ao mínimo de 16 páginas.

Depois:

- verifica PMM_KEEP;
- limita o pedido às páginas disponíveis;
- tenta pmm_alloc_contig(pages);
- se falhar, tenta novamente com exatamente 16 páginas;
- se falhar novamente, o crescimento termina sem arena.

Assim uma alocação pode falhar mesmo quando o PMM possui muitas páginas livres no total, caso não exista run físico contíguo adequado.

## Ordem de locks

O source documenta a relação:

~~~text
heap_lock -> pmm_lock
~~~

kmalloc mantém heap_lock durante heap_grow, que chama funções do PMM.

A relação inversa precisa ser proibida.

O PMM declara explicitamente que não deve alocar por heap.

Isso mantém a dependência acíclica:

~~~text
heap pode entrar no PMM
PMM não pode entrar no heap
~~~

Caso contrário seria possível:

~~~text
CPU A: heap_lock -> espera pmm_lock
CPU B: pmm_lock  -> espera heap_lock
~~~

e o kernel ficaria em deadlock.

A ordem de locks é parte do contrato do allocator.

## Busca first-fit

kmalloc_in_arenas percorre arenas em ordem.

Dentro de cada arena, percorre blocos desde a base.

Seleciona o primeiro que satisfaz:

~~~text
used == 0
size >= need
~~~

A política é portanto first-fit.

Com B blocos totais, uma busca sem sucesso pode custar O(B).

Não existem free lists segregadas, árvores por tamanho, slab caches ou buddy allocator interno ao heap.

## Split

Para bloco livre de tamanho F e request alinhado N:

~~~text
leftover = F - N
~~~

Um novo bloco livre só é criado quando:

~~~text
leftover >= HEAP_USER_OFF + HEAP_ALIGN
         >= 16 + 16
         >= 32 bytes
~~~

Isso garante espaço para novo header e pelo menos 16 bytes de payload.

O header do split é criado logo após o payload alocado.

O bloco selecionado passa a ter size = N e used = 1.

Se sobram menos de 32 bytes, esse tail é absorvido pela alocação e se torna fragmentação interna.

## kfree

kfree(null) é no-op.

Para ponteiro não nulo, exige:

- heap inicializado;
- alinhamento de 16 bytes;
- endereço dentro de alguma arena;
- header calculado marcado como usado.

Em sucesso, used passa a zero e coalesce_forward é executado.

Double-free detectado provoca panic.

Ponteiro fora das arenas também provoca panic.

## Limitação na validação de ponteiro

A validação atual não é completa.

arena_of_user confirma que o endereço está dentro de uma arena e a checagem de alinhamento confirma boundary de 16 bytes.

Depois o allocator simplesmente calcula:

~~~text
block = user - 16
~~~

Não existe uma caminhada prévia comprovando que esse endereço corresponde exatamente ao início do payload de um bloco real.

Logo, um endereço interno alinhado a 16 bytes pode fazer bytes do payload serem interpretados como heap_block.

Dependendo do conteúdo, isso pode causar panic ou corrupção de metadata.

Hardening futuro poderia incluir:

- magic em headers;
- boundary tags;
- verificação por traversal;
- canaries;
- red zones.

## Coalescing somente para frente

coalesce_forward une o bloco liberado com blocos livres imediatamente seguintes.

Ele não procura bloco anterior.

Isso torna fragmentação dependente da ordem de free.

Se B é liberado primeiro e depois A, ao liberar A ele encontra B à frente e pode unir.

Se A é liberado primeiro e depois B, liberar B não volta para unir com A.

Assim blocos livres adjacentes podem permanecer separados.

Isso decorre do layout simples sem ponteiro para bloco anterior nem boundary tag.

## Lifetime das arenas

kfree não devolve arena vazia ao PMM.

Mesmo quando todos os blocos de uma arena ficam livres, as páginas permanecem pertencendo ao heap.

O lifetime da arena é praticamente até reboot.

Vantagens:

- não precisa remover arena durante traversal concorrente;
- não precisa reconstruir contiguidade física;
- futuras alocações reutilizam a capacidade rapidamente.

Custos:

- PMM não recupera arenas ociosas;
- crescimento do heap transfere permanentemente páginas para esse pool.

Uma futura arena reclamation exigiria sincronização e transferência de ownership explícita de volta ao PMM.

## Conteúdo das alocações

kmalloc não zera o payload.

Bloco reutilizado pode conter dados do dono anterior.

Callers precisam inicializar a memória quando necessário.

Isso é comportamento típico de malloc, mas importa quando dados podem atravessar trust boundaries.

heap.h não oferece atualmente kcalloc nem variante zeroing.

## Accounting

heap_tally percorre todos os blocos e soma payloads usados/livres.

heap_used_bytes e heap_free_bytes fazem isso sob heap_lock.

Essas métricas não incluem:

- 16 bytes de header por bloco;
- fragmentação interna absorvida;
- estruturas do PMM;
- overhead de espaço virtual.

São métricas do payload do allocator, não custo físico total exato.

heap_arena_count devolve narenas protegido pelo mesmo lock.

## Concorrência

Todas as operações normais de heap são serializadas por um único heap_lock.

Isso simplifica consistência e permite cross-CPU free.

Uma CPU pode alocar e outra liberar o mesmo bloco, desde que o protocolo de ownership do objeto permita.

tools/test_pmm_heap_smp testa explicitamente esse caso.

O custo é escalabilidade: kmalloc, kfree e accounting competem pelo mesmo lock global.

Não existem caches por CPU nem locks por arena.

## Exemplos de ownership

O heap é usado por vários subsistemas:

- stacks de kthreads;
- backbuffers e buffers 3D;
- compiladores/linkers;
- CLVM;
- filesystem;
- rede;
- shaders.

O allocator não armazena quem é o owner.

Ownership nasce do control flow do subsistema.

Exemplo: kthread_create aloca stack privada. Em kthread_join, o slot é desacoplado da stack sob g_slot_lock; o slot lock é liberado; só então kfree é chamado.

Essa ordem evita entrar no heap enquanto mantém o lock de slot e deixa o teardown explícito.

## Falhas de alocação como transações

Callers que alocam vários recursos precisam tratar o processo como transação.

Padrão:

~~~text
aloca A
aloca B
se B falha:
    libera A
    retorna erro
~~~

O repositório contém vários caminhos desse tipo.

O heap não consegue inferir qual subsistema deve liberar um bloco. Ele conhece apenas estado used/free.

## Self-test

heap_selftest valida:

1. alocações 16, 64 e 256;
2. ponteiros distintos;
3. alinhamento 16;
4. preservação do conteúdo;
5. reuso exato do bloco intermediário de 64 após free;
6. ausência de corrupção dos vizinhos;
7. métricas used/free.

A exigência de reutilizar exatamente o mesmo endereço evidencia a política first-fit atual.

## Teste SMP host

tools/test_pmm_heap_smp utiliza quatro pthread workers.

Primeiro testa PMM concorrente.

Depois testa o heap:

- alinhamento/reuso/accounting single-thread;
- quatro threads alocando e liberando simultaneamente;
- tamanhos variáveis;
- escrita em blocos vivos;
- cross-CPU free.

No teste final, um bloco alocado com identidade CPU 0 é liberado depois de host_set_cpu(2).

Isso comprova que o heap não exige free na mesma CPU que alocou.

Ainda não é prova formal de ausência de todas as races.

## Modos de falha

### Uso antes da inicialização

kmalloc, kfree e accounting entram em panic.

### Reserva física atingida

heap_grow falha em vez de consumir PMM_KEEP.

### Fragmentação física

pmm_alloc_contig pode falhar com memória total suficiente.

### Limite de arenas

Máximo 32.

### Double free

Detectado por used == 0 e tratado como panic.

### Ponteiro estrangeiro

Endereço fora das arenas é recusado.

### Ponteiro interno alinhado

Não é completamente validado e pode ser interpretado como header.

### Fragmentação lógica

First-fit e coalescing apenas para frente podem deixar capacidade total suficiente, mas dividida em blocos inadequados.

## Segurança e robustez

Propriedades atuais positivas:

- checagem de alinhamento;
- bounds por arena;
- detecção de double free;
- metadata protegida por lock;
- reserva de memória física;
- PMM contabiliza páginas transferidas às arenas.

Hardening ainda ausente:

- canaries;
- red zones;
- guard pages;
- poison em free;
- zero-on-allocate;
- quarantine de objetos liberados;
- metadata de owner/tipo;
- validação exata de boundary.

Portanto é um allocator funcional de kernel, não um allocator hardened de debug.

## Performance

A busca first-fit domina o caminho normal.

Hit precoce é barato; hit tardio ou falha percorre muitos blocos.

Split é O(1).

coalesce_forward pode percorrer K blocos livres seguintes, logo free pode custar O(K).

heap_tally é O(B).

Crescimento inclui o custo da busca física contígua no PMM.

Tudo é serializado por um lock global.

## Limitações atuais

Na revisão analisada:

- no máximo 32 arenas;
- arena mínima de 64 KiB;
- arenas exigem backing físico contíguo;
- arenas nunca retornam ao PMM;
- um heap_lock global;
- first-fit;
- sem backward coalescing;
- sem realloc/calloc/aligned alloc;
- payload não é zerado;
- sem hardening de metadata;
- kfree não prova completamente que recebeu exatamente uma allocation boundary.

Esses são fatos do código atual.

## Fronteira de revisão

Este capítulo foi reconciliado com ChrisOS main na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

A cadeia atual de ownership é:

~~~text
PMM possui páginas físicas livres
   -> heap reivindica páginas contíguas
   -> arena passa a possuir essas páginas
   -> bloco alocado transfere uso do payload ao caller
   -> kfree devolve o bloco à arena
   -> arena mantém as páginas para futuras alocações
~~~

Reclamation de arenas, slabs, caches por CPU ou metadata hardened exigirão atualização desse modelo.
