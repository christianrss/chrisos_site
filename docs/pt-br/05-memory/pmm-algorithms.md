---
id: pmm-algorithms
lang: pt-br
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/heap.c
  - kernel/metal/spin.c
  - kernel/metal/spin.h
  - kernel/metal/smp.c
  - kernel/metal/bootinfo.c
symbols:
  - pmm_alloc
  - pmm_alloc_contig
  - pmm_claim_at
  - pmm_free_contig
  - pmm_foreach_free_run
  - scan_usable_for_run
  - claim_run
  - pmm_enter
  - pmm_leave
  - pmm_reserve_dma32
depends_on:
  - physical-memory
  - data-structures
  - algorithmic-complexity
related:
  - hhdm
  - heap-ownership
  - spinlocks
  - resource-lifetime
---

# Algoritmos e invariantes do PMM

## Escopo

O capítulo de memória física define o que o PMM possui. Este capítulo concentra-se em **como o allocator atual procura, reclama, libera e sincroniza frames**.

A implementação combina:

- um bit por frame;
- filtro pelo memory map do Limine;
- cursor semelhante a next-fit para uma página;
- otimização de skip por byte;
- enumeração de runs livres;
- validação all-or-nothing de claims;
- lock recursivo por CPU;
- uma segunda máscara para subalocação DMA32.

O ponto central não é apenas a estrutura de dados, mas os invariantes entre todas essas estruturas.

![Estado do bitmap, scans, claims, frees e subpool DMA32](../../assets/diagrams/pmm-allocation-state-pt-br.svg)

## Representação central

Para frame físico (i):

```text
byte_index = i / 8
bit_index  = i % 8
used(i)    = bitmap[byte_index] & (1 << bit_index)
```

A consulta e mudança de bit são O(1).

Um bit não codifica:

- owner;
- reference count;
- generation;
- tipo do memory map;
- nó NUMA;
- estado zeroed/dirty.

Essas propriedades estão fora do PMM ou não são modeladas.

O estado interno é deliberadamente simples:

```text
0 = candidato livre dentro de USABLE
1 = indisponível para o allocator geral
```

## Invariante: scan apenas em USABLE

O bitmap sozinho não define allocatability.

`scan_usable_for_run` e `pmm_foreach_free_run` percorrem o memory map e examinam somente entradas `LIMINE_MEMMAP_USABLE`.

Assim:

```text
allocatable(frame) =
    frame está em intervalo USABLE
    AND bit do bitmap está zero
    AND frame está abaixo de PMM_MAX_PHYS
```

Isso é mais forte que “bit zero”.

O tipo do memory map não está embutido no bitmap.

## Invariante de inicialização

O allocator começa com todos os bits em 1.

Somente páginas completas de ranges USABLE são limpas.

Ranges protegidos permanecem ou voltam para 1.

O invariante pretendido depois do init é:

> Qualquer frame retornável está com bit zero, dentro de entrada USABLE e abaixo de 32 GiB.

O primeiro 1 MiB é reservado adicionalmente.

A política “unknown = indisponível” reduz risco de alocar firmware/device memory.

## Busca semelhante a next-fit

`pmm_alloc` procura a partir de `pmm_cursor`:

```text
result = scan_usable_for_run(1, cursor)
if result == 0:
    result = scan_usable_for_run(1, 0)
```

Após claim:

```text
cursor = base + pages * 4096
```

O comportamento é semelhante a next-fit porque o hint avança.

Não é implementação circular clássica única; existe uma chamada explícita de fallback a partir de zero.

Isso reduz rescans repetitivos de endereços baixos no caso comum.

## Rollback do cursor no free

`pmm_free_contig` faz:

```text
if freed_phys < cursor:
    cursor = freed_phys
```

Assim um endereço baixo liberado volta rapidamente ao caminho de busca.

Sem isso, cursor alto poderia ignorar holes reutilizáveis até o próximo wrap.

A política não garante que o frame recém-liberado será exatamente o próximo resultado, pois outro frame livre pode aparecer antes no scan.

## Limites do scan

Em cada range USABLE:

```text
addr = align_up(base, 4096)
end  = align_down(base + length, 4096)
end  = min(end, PMM_MAX_PHYS)
```

Quando `from_phys` está acima do início, o começo é elevado para `align_up(from_phys)`.

Um run não atravessa automaticamente fronteira entre duas entradas do memory map. O estado é reiniciado por entrada.

Isso é conservador porque ranges adjacentes numericamente podem ter histórico/semântica distintos no firmware.

## Skip de oito páginas

Um byte do bitmap representa oito frames.

Quando:

```text
page % 8 == 0
AND bitmap[page / 8] == 0xFF
```

o allocator avança oito páginas:

```text
8 * 4096 = 32 KiB
```

em uma operação lógica.

A otimização depende de alinhamento ao primeiro bit do byte.

Ela melhora o custo constante em áreas densamente usadas, embora o pior caso permaneça linear.

## Máquina de estados do run

Para pedido `count`, o scanner mantém:

- `run`: número atual de páginas consecutivas livres;
- `run_start`: início físico do candidato.

Pseudo-código:

```text
run = 0

para cada página:
    se usada:
        run = 0
        run_start = próxima
    senão:
        se run == 0:
            run_start = página
        run++

        se run == count:
            claim(run_start, count)
            return run_start
```

O detector usa O(1) de estado auxiliar.

## Claim como transição separada

`claim_run` pressupõe que caller já verificou validade.

Ele não repete todas as verificações.

Para cada página:

1. liga bit;
2. reduz free;
3. aumenta used.

Depois avança cursor.

Como é função `static`, somente código interno do PMM pode chamá-la diretamente.

A separação reduz código no hot path, mas exige que callers internos mantenham o precondition.

## pmm_claim_at e atomicidade lógica

`pmm_claim_at` é API usada por outras partes do kernel. Ela não pode confiar que um extent observado anteriormente ainda esteja livre.

Primeiro valida todas as páginas:

- count não zero;
- base não zero;
- alinhamento/teto físico;
- bit ainda zero.

Só depois executa o claim.

Como o lock cobre validação e mutation, outra CPU não consegue roubar uma página entre as fases.

O resultado é all-or-nothing.

## pmm_foreach_free_run

A enumeração de runs é primitive algorítmica.

Ela percorre USABLE e chama callback uma vez para cada run livre maximal.

Retorno zero do callback encerra a busca.

O heap usa a interface para consumir extents no init.

O PMM não cria lista temporária de runs, evitando dependência circular com heap.

## Por que o lock precisa ser recursivo

`pmm_foreach_free_run` mantém `pmm_lock`.

O callback do heap pode chamar `pmm_claim_at`.

Então:

```text
pmm_foreach_free_run
    possui pmm_lock
    -> callback do heap
        -> pmm_claim_at
            -> pmm_enter novamente
```

Spinlock normal não reentrante causaria self-deadlock.

O PMM mantém `pmm_depth[cpu]` e incrementa depth na reentrada da mesma CPU.

A recursão existe para esse desenho concreto de callback, não como autorização genérica para qualquer ciclo.

## Invariante do estado de interrupção

A entrada externa usa `irq_save`:

1. salva RFLAGS;
2. executa `cli`;
3. pega spinlock.

O leave externo solta lock e restaura IF somente se estava ligado antes.

O invariante é:

> Enquanto uma CPU possui o PMM no depth externo, IRQ mascarável na mesma CPU não pode reentrar e confundir o mecanismo de recursão.

Sem `cli`, handler executado com `pmm_depth[cpu] > 0` poderia ser interpretado como recursão legítima sem representar a mesma call chain.

## Estado indexado por CPU

Depth e flags salvos são arrays indexados por `smp_current_cpu()`.

Índice maior ou igual a `SMP_CPU_CAP` cai para zero.

No caminho normal, cada CPU online precisa ter identidade estável e exclusiva.

O fallback é defensivo; colisão real de identidade em uso concorrente faria CPUs compartilharem bookkeeping de recursão incorretamente.

Portanto identidade SMP correta é dependência implícita do PMM.

## Ordem de locks

O heap documenta:

```text
heap lock -> PMM lock
```

PMM não adquire heap lock.

Isso cria uma ordem parcial que evita ciclo simples.

A enumeração com callback é exceção controlada porque PMM chama código do caller enquanto está locked. O callback precisa obedecer regras restritas de reentrada e não introduzir ordem inversa.

## Complexidade de uma página

Se P páginas forem examinadas:

- melhor caso próximo de O(1) quando cursor aponta para livre;
- pior caso O(P).

Skip de byte permite testar oito páginas usadas em uma comparação.

Padrões esparsos com pelo menos um bit zero por byte reduzem a utilidade do skip e aproximam o pior caso de inspeção por página.

## Estratégia contígua

`pmm_alloc_contig(k)` procura primeiro run maximal livre com pelo menos k páginas através de `pmm_foreach_free_run`.

Isso é first-fit na ordem do memory map.

Depois `pmm_claim_at` valida e reclama.

Há fallback para scanner a partir de zero.

Não existe best-fit nem escolha orientada a reduzir fragmentação.

O primeiro run suficiente vence.

## Fragmentação externa

Considere:

```text
[2 páginas] [1] [7] [3]
```

Pedido de seis páginas usa o run de sete.

Após sequência longa de alloc/free com tamanhos variados, total livre pode ser grande e maior run pode ser pequeno.

Assim:

```text
free_count >= requested
```

não implica:

```text
pmm_alloc_contig(requested) != 0
```

O bitmap não move frames para compactar RAM.

## Semântica do free

`pmm_free_contig(base, k)` valida range/alinhamento.

Frame inválido causa panic.

Bit 1 é limpo e counters são ajustados.

Bit já zero é ignorado.

Isso torna a operação idempotente no nível do bit, mas pode ocultar ownership bug.

Não existe owner table capaz de distinguir “free repetido” de estado legitimamente livre.

## Invariante dos counters

Claims/frees válidos devem preservar:

```text
usable = used + free
```

onde usable é o pool depois das reservas estáticas.

Se caller liberar frame reservado que não correspondia a alocação dinâmica, counters podem perder significado.

Logo o invariante depende de preconditions de ownership, não apenas de arithmetic interna.

## DMA32 como allocator aninhado

DMA32 possui duas camadas.

Primeiro o PMM geral reclama 16 páginas.

Depois máscara de 16 bits gerencia subranges.

Para pedido k:

```text
need = (1 << k) - 1

para i:
    mask = need << i
    se (dma32_free & mask) == mask:
        limpar mask
        retornar base + i * 4096
```

É first-fit minúsculo sobre bits.

O espaço máximo é fixo em 16 páginas, então custo é praticamente constante.

## Fragmentação no DMA32

Mesmo em 16 páginas, distribuição importa.

Exemplo:

```text
1111000011110000
```

Pode haver oito páginas livres no total sem existir run livre de oito.

A diferença entre capacidade total e capacidade contígua aparece em escala pequena também.

A simplicidade do pool justifica scan linear de bits.

## Fronteira de ownership DMA32

No bitmap global, as 16 páginas ficam permanentemente em estado used enquanto o pool existe.

`pmm_free_dma32` altera apenas `dma32_free`.

Logo uma página interna livre no suballocator não reaparece no PMM geral.

Isso impede double allocation entre os dois allocators.

## Custo de inicialização

Init executa componentes lineares:

- preencher bitmap de 1 MiB;
- percorrer memory map;
- liberar USABLE página a página;
- reservar ranges página a página;
- encontrar run DMA32.

Com P páginas processadas, custo é O(P).

O teto fixo representa no máximo 8.388.608 frames.

Esse custo ocorre uma vez no boot.

## Diferença para buddy allocator

Buddy allocator mantém listas por ordens potência de dois.

Ele encontra blocos alinhados e pode fundir buddies livres.

O ChrisOS atual não implementa essas listas ou merges.

Bitmap tem vantagens:

- estado conceitual pequeno;
- status de página em O(1);
- inicialização simples;
- nenhuma dependência do heap.

Custos:

- busca linear;
- contiguidade mais frágil sob fragmentação;
- nenhum metadata de coalescing por ordem.

Trocar o algoritmo deve responder a necessidade medida, não apenas preferência terminológica.

## Caches per-CPU

Hoje todos os allocs gerais passam pelo lock global.

Carga SMP maior pode criar contenção.

Uma extensão comum é cache de páginas livres por CPU, reabastecido em batches.

O ChrisOS não possui essa camada.

Ela também complicaria counters: página em cache local está livre para o CPU, mas pode não estar na estrutura global.

## Estratégia de validação

Testes fortes precisam verificar invariantes.

Casos úteis:

- alocar até exhaustion sem duplicidade;
- free/realloc e restauração de counters;
- sequência aleatória comparada a reference model;
- contiguidade sob fragmentação controlada;
- colisão em `pmm_claim_at`;
- runs em fronteiras do memory map;
- stress SMP;
- reentrada com interrupções;
- fragmentação/reuso DMA32;
- double free intencional para caracterizar comportamento atual;
- free desalinhado/fora do range;
- equality de counters após toda transição válida.

O self-test embutido cobre somente unicidade básica, integridade via HHDM e reuso de página liberada.

## Diagnóstico de falhas

Bugs do PMM aparecem longe da origem:

- page tables corrompidas;
- memória de processo mudando;
- metadata do heap destruído;
- descriptors de device alterados;
- sintomas estranhos de TLB.

Informações úteis seriam:

- endereço físico;
- byte/bit;
- cursor;
- counters;
- caller;
- CPU;
- membership no DMA32;
- range/tipo do memory map.

A representação atual guarda apenas parte disso.

## Limitações atuais

O PMM não possui:

- detecção estrita de double free;
- provenance/owner;
- reference count;
- cache per-CPU;
- NUMA;
- buddy orders;
- compactação;
- zones completas;
- política adaptativa de scan;
- limite de latência determinístico.

Assim worst-case de allocation cresce com a memória percorrida.

É um desenho adequado a kernel experimental pequeno, mas os limites importam conforme RAM e concorrência crescem.

## Mapa de fonte

Primitives de bitmap, cursor, detector de runs, claim/free, DMA32 e lock recursivo estão em `kernel/metal/pmm.c`.

`kernel/metal/heap.c` mostra o caso concreto de callback/reentrada.

`kernel/metal/spin.c`/`spin.h` implementam lock CAS e save/restore de IF.

`kernel/metal/smp.c` fornece identidade de CPU usada pelo bookkeeping recursivo.

As afirmações foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
