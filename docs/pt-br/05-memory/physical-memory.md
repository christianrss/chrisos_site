---
id: physical-memory
lang: pt-br
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/spin.c
  - kernel/metal/spin.h
  - kernel/metal/heap.c
symbols:
  - pmm_init
  - pmm_alloc
  - pmm_alloc_contig
  - pmm_alloc_dma32
  - pmm_free
  - pmm_free_contig
  - pmm_foreach_free_run
  - pmm_claim_at
  - pmm_usable_pages
  - pmm_used_pages
  - pmm_free_pages
  - pmm_selftest
  - bootinfo_phys_to_virt
depends_on:
  - atom-semiconductor
  - x86-64-memory-privilege
related:
  - hhdm
  - pmm-algorithms
  - virtual-memory
  - heap-ownership
---

# Gerenciamento de memória física

## Escopo

O physical memory manager (PMM) responde à pergunta que existe abaixo da memória virtual e do heap: **quais frames físicos de 4 KiB podem ser entregues a um novo owner e quais já estão reservados ou alocados?**

Frame físico não é alocação C e não é mapping virtual. O PMM devolve endereços físicos. Outras camadas decidem se esses frames vão sustentar page tables, páginas de processo, arenas de heap, buffers DMA, recursos gráficos ou outras estruturas do kernel. Para dereferenciar RAM comum, o kernel precisa de um mapping virtual adequado; no ChrisOS isso normalmente ocorre através do higher-half direct map (HHDM) fornecido pelo Limine.

O PMM atual do ChrisOS é um allocator por bitmap, limitado e estático, com:

- unidades de 4 KiB;
- teto físico fixo em 32 GiB;
- um bit de estado por frame gerenciado;
- cursor semelhante a next-fit para alocação de uma página;
- enumeração de runs livres e first-fit para contiguidade;
- subpool DMA32 dedicado de 16 páginas;
- spinlock com interrupções desabilitadas e recursão deliberada na mesma CPU;
- contadores para o pool alocável;
- self-test executado cedo no boot.

Este capítulo descreve a implementação existente na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Não substitui o código por um buddy allocator ou por um modelo NUMA de livro-texto.

## Frames físicos versus endereços virtuais

O ChrisOS define:

```text
PMM_PAGE     = 4.096 bytes
PMM_MAX_PHYS = 32 GiB
```

O retorno de `pmm_alloc()` é um endereço físico alinhado a 4 KiB. Ele não é automaticamente um ponteiro válido no address space atual.

Para RAM comum, código do kernel pode usar:

```text
virtual = physical + hhdm_offset
```

através de `bootinfo_phys_to_virt`. O helper exige bootinfo inicializado e soma o offset do HHDM.

A separação é essencial:

- ownership no PMM determina se um frame pode ser reutilizado;
- page tables determinam quais endereços virtuais traduzem para o frame;
- HHDM fornece um alias de kernel conveniente para RAM física comum;
- regiões MMIO exigem mappings com atributos apropriados e não devem ser tratadas como RAM apenas porque possuem endereço físico.

Remover um mapping virtual não devolve automaticamente o frame ao PMM. Da mesma forma, alocar um frame não cria por si só um mapping em processo.

## Espaço físico gerenciado e tamanho do bitmap

O teto de 32 GiB resulta em:

```text
32 GiB / 4 KiB = 8.388.608 frames
```

Com um bit por frame:

```text
8.388.608 / 8 = 1.048.576 bytes
```

Logo `pmm_bitmap` ocupa 1 MiB estático.

Esse metadata existe independentemente da quantidade de RAM instalada. A vantagem é possuir estado determinístico, sem depender do heap, disponível antes de `heap_init`. O custo é um footprint fixo de 1 MiB e um limite arquitetural explícito: memória física em 32 GiB ou acima não pode ser representada nem alocada por esse PMM.

A transformação de endereço físico em posição do bitmap é:

```text
page = phys / 4096
byte = page / 8
bit  = page % 8
```

Bit 1 significa usado/reservado; bit 0 significa livre.

Consulta e mudança de um bit isolado custam O(1).

## Inicialização: começar com tudo reservado

`pmm_init` preenche o bitmap inteiro com `0xFF`. Portanto todo frame representável começa no estado mais conservador: indisponível.

Somente páginas explicitamente pertencentes a entradas `LIMINE_MEMMAP_USABLE` são liberadas.

Essa direção evita depender de uma lista completa de todos os tipos proibidos. Qualquer categoria desconhecida, de firmware ou não suportada permanece reservada por padrão.

A sequência lógica é:

```text
inicializar lock do PMM
marcar todos os frames como usados
free_count = 0
used = 0
usable = 0

para cada entrada Limine:
    se type == USABLE:
        liberar frames completos de 4 KiB

reservar físico 0 .. 1 MiB

para categorias reservadas/não RAM:
    marcar frames tocados como usados

usable = free_count
used = 0
cursor = 0

reservar pool DMA32
```

A categoria executable/modules é marcada novamente em um segundo loop na revisão atual. Como marcar bit já utilizado é operação idempotente, isso não desconta a mesma página duas vezes de `pmm_free_count`.

## Regras de alinhamento do memory map

Ranges do firmware podem começar ou terminar fora de fronteiras de página. O PMM trata ranges utilizáveis e protegidos em direções opostas.

Para memória utilizável:

```text
inicio = align_up(base, 4 KiB)
fim    = align_down(base + length, 4 KiB)
```

Somente frames completamente contidos na região tornam-se livres.

Para ranges reservados:

```text
inicio = align_down(base, 4 KiB)
fim    = align_up(base + length, 4 KiB)
```

Qualquer frame tocado pelo range protegido permanece indisponível.

Esse comportamento evita entregar ao allocator páginas parcialmente ocupadas por firmware, framebuffer ou outros objetos.

## Categorias do memory map e política de reclaim

Como o bitmap começa todo ocupado, qualquer tipo diferente de USABLE permanece reservado mesmo sem tratamento especial. O código ainda marca explicitamente como usados:

- memória reserved;
- ACPI NVS;
- bad memory;
- bootloader reclaimable;
- executable/modules;
- framebuffer.

O primeiro 1 MiB é reservado independentemente da categoria informada pelo Limine.

O PMM atual não possui uma fase posterior que transforme bootloader-reclaimable ou outras categorias recuperáveis em páginas comuns. Portanto “reclaimable” no protocolo de boot não significa que o ChrisOS já execute esse reclaim.

A imagem do kernel fica protegida pela classificação do memory map fornecido pelo bootloader, e não por uma conversão direta dos símbolos `__kernel_start` e `__kernel_end` em ranges físicos. Esses símbolos são usados no log diagnóstico.

## Semântica dos contadores

O PMM expõe:

- `pmm_usable`;
- `pmm_used`;
- `pmm_free_count`.

Esses valores não significam “toda RAM física do computador”.

Depois que as reservas estáticas são aplicadas, `pmm_usable` recebe o número de frames que compõem o pool alocável. Em seguida `pmm_used` é zerado. Reservas de firmware/kernel não entram no contador de alocações dinâmicas.

Claims normais incrementam `pmm_used` e decrementam `pmm_free_count`. Free válido faz o inverso.

O pool DMA32 é reservado depois que `pmm_usable` foi fixado. Assim suas 16 páginas passam a aparecer como usadas dentro do pool alocável. Sob operações válidas, o invariante pretendido é:

```text
pmm_usable = pmm_used + pmm_free_count
```

Ele descreve o conjunto alocável depois das reservas iniciais, não todo o espaço físico.

## Alocação de uma página

`pmm_alloc` entra na região crítica e chama `scan_usable_for_run(1, pmm_cursor)`.

Se não encontrar página no cursor ou depois dele, repete a busca a partir do endereço físico zero.

A política é semelhante a next-fit:

1. procurar depois do último claim;
2. fazer wrap para o início quando necessário;
3. retornar zero quando o pool não possui frame livre.

Endereço físico zero nunca é uma alocação válida porque o primeiro 1 MiB está reservado. Assim zero pode funcionar sem ambiguidade como sentinel de falha.

Ao reclamar uma sequência, `claim_run`:

- liga os bits do bitmap;
- reduz free count;
- incrementa used count;
- move `pmm_cursor` para o primeiro byte depois do run.

Quando um frame de endereço menor é liberado, `pmm_free_contig` reduz o cursor para esse endereço. Isso torna páginas recém-liberadas em regiões inferiores candidatas a reutilização precoce.

## Otimização do scan

`scan_usable_for_run` percorre exclusivamente entradas do memory map marcadas USABLE. Um bit eventualmente limpo fora dessas regiões não é encontrado pela busca comum.

Quando o endereço atual coincide com o primeiro bit de um byte do bitmap e esse byte vale `0xFF`, o algoritmo pula oito páginas usadas de uma vez.

Isso reduz o custo constante ao atravessar regiões completamente ocupadas.

No pior caso a busca continua O(P), onde P é o número de páginas utilizáveis examinadas, mas spans totalmente usados podem ser avançados em blocos de oito frames.

## Alocação fisicamente contígua

`pmm_alloc_contig(count)` não chama `pmm_alloc` repetidamente. Ele procura um run livre que já possua o tamanho solicitado.

Primeiro executa `pmm_foreach_free_run`. O callback para no primeiro run com pelo menos `count` páginas. O intervalo selecionado é reclamado com `pmm_claim_at`.

Se esse caminho não resultar em endereço válido, existe fallback para `scan_usable_for_run(count, 0)`.

Uma alocação de (k) páginas representa:

```text
intervalo físico = [base, base + k * 4096)
```

e cada frame do intervalo precisa estar livre no momento do claim.

Encontrar o run pode custar O(P). Validar e marcar o run custa O(k).

Contiguidade física é diferente de contiguidade virtual. Um buffer virtual poderia ser construído a partir de frames dispersos, mas hardware sem scatter/gather ou certas estruturas físicas podem exigir endereços consecutivos reais.

## Enumeração de runs livres

`pmm_foreach_free_run(cb, user)` expõe extents físicos disponíveis a outras camadas.

Para cada range USABLE ele:

1. alinha para páginas completas;
2. limita o final a 32 GiB;
3. percorre bits do bitmap;
4. agrega páginas livres consecutivas;
5. chama o callback no fim de cada run;
6. encerra a enumeração se o callback retornar zero.

O heap usa essa API durante sua inicialização. O callback pode chamar `pmm_claim_at` enquanto a enumeração ainda possui o lock do PMM; essa é a razão prática para a recursão por CPU.

A interface evita construir uma lista temporária de extents usando o próprio heap antes de o heap estar funcional.

## Claim em endereço escolhido

`pmm_claim_at(phys, pages)` serve para um caller que já selecionou um extent.

Antes de alterar qualquer bit, ele verifica todo o intervalo:

- quantidade de páginas diferente de zero;
- base diferente de zero;
- alinhamento e teto físico através de `page_in_range`;
- todos os bits ainda livres.

Somente depois da validação completa executa `claim_run`.

Isso evita claim parcial: o allocator não marca as primeiras páginas para depois descobrir colisão no final.

O custo é O(k) para validar e O(k) para efetivar o claim.

## Liberação de frames

`pmm_free` é apenas wrapper de uma página para `pmm_free_contig`.

A função contígua retorna silenciosamente quando base ou count são zero. Para cada frame real, porém, valida alinhamento e teto de 32 GiB; endereço inválido causa `panic`.

Se o bit está usado, ele é limpo, free count cresce e used count diminui quando maior que zero.

Uma propriedade importante da revisão atual é que **double free de bit já livre não dispara panic**. A rotina simplesmente mantém o bit em zero. Também não existe tabela de provenance ou owner que prove que o caller possui aquela página.

Portanto ownership correto depende da disciplina das camadas consumidoras. Isso contrasta com o heap, cujo `kfree` verifica explicitamente bloco já livre.

Uma versão de debug futura poderia registrar owner, poison, generation ou tratar double free como violação fatal.

## Locking e recursão na mesma CPU

O estado global do PMM é protegido por `pmm_lock`.

A entrada externa em `pmm_enter`:

1. obtém o índice da CPU;
2. salva flags e desabilita interrupções via `irq_save`;
3. adquire o spinlock;
4. define depth 1 para aquela CPU.

Se a mesma CPU entra novamente enquanto `pmm_depth[cpu] > 0`, apenas incrementa o depth e não tenta adquirir o spinlock outra vez.

Leaves internos decrementam o depth. O leave externo libera o lock e restaura IF apenas se estava habilitado antes da entrada.

Essa recursão é deliberada. Durante `heap_init`, `pmm_foreach_free_run` segura PMM; o callback do heap pode chamar `pmm_claim_at`, reentrando no allocator.

Sem esse mecanismo, o spinlock não reentrante entraria em deadlock.

## Ordem de locks com o heap

O código documenta a direção:

```text
heap lock -> PMM lock
```

O PMM não deve depender de alocação do heap.

Essa regra impede o ciclo clássico:

```text
heap possui heap_lock e espera PMM
PMM possui pmm_lock e espera heap
```

Bitmap, counters e arrays de recursão são estáticos justamente para que o PMM funcione sem `kmalloc`.

## Subpool DMA32

Alguns devices não conseguem endereçar memória acima de 4 GiB. O ChrisOS separa um pequeno pool DMA32 durante `pmm_init`.

Seu tamanho é:

```text
16 páginas * 4 KiB = 64 KiB
```

`pmm_reserve_dma32` reclama um run de 16 páginas pelo scanner normal e depois verifica se o final continua abaixo do limite de 4 GiB.

No sucesso:

- `dma32_base` guarda a base física;
- os 16 frames permanecem marcados como usados no bitmap global;
- `dma32_free` vira máscara de 16 bits de disponibilidade, armazenada em inteiro de 32 bits.

`pmm_alloc_dma32(pages)` procura bits 1 consecutivos nessa máscara e os limpa ao alocar.

Existem, portanto, duas camadas de ownership:

```text
PMM global: arena inteira de 64 KiB já está claimed
máscara DMA32: páginas internas podem estar livres ou ocupadas
```

Por isso alloc/free dentro do DMA32 não altera `pmm_used` ou `pmm_free_count`: o pool já saiu do allocator geral na reserva inicial.

## Limitações do DMA32

Pedidos falham quando:

- não existe pool;
- pages é zero;
- pages > 16;
- não há run de bits livres com o comprimento pedido.

`pmm_free_dma32` apenas devolve bits à máscara secundária e nunca libera a arena física para o PMM geral.

A reserva pede primeiro ao scanner normal um run de 16 páginas e somente depois verifica o limite de 4 GiB. O scanner não recebe uma zona “abaixo de 4 GiB” como parâmetro. Isso atende ao layout esperado e ao uso pequeno orientado a UHCI, mas não equivale a um allocator de zones completo.

Um sistema maior normalmente separaria DMA32, normal e outras zonas de forma explícita.

## Política PMM_KEEP e heap

`PMM_KEEP` vale 32 MiB, mas essa reserva é aplicada pela camada de heap, não pelo algoritmo básico de `pmm_alloc`.

O heap calcula quantas páginas precisa preservar fora de suas arenas e se recusa a consumir o PMM abaixo desse limite.

Assim:

- PMM expõe frames disponíveis;
- heap decide quanto desse conjunto pode transformar em arenas.

A separação evita que o physical allocator precise incorporar políticas de todos os consumidores.

## Resumo de complexidade

| Operação | Estratégia atual | Pior caso |
|---|---|---:|
| Consultar bit | índice direto | O(1) |
| Alocar uma página | cursor + wrap | O(P) |
| Alocar contíguo | first-fit de run | O(P + k) |
| Claim de run conhecido | validar + marcar | O(k) |
| Liberar k páginas | limpar linearmente | O(k) |
| Enumerar runs | walk de memmap/bitmap | O(P) |
| Alocar DMA32 | scan de até 16 bits | O(16) |
| Ler counters | lock + leitura | O(1) |

P é o número de páginas percorridas; k é o tamanho do run pedido.

O skip de bytes `0xFF` melhora o custo constante de áreas totalmente usadas, mas não muda o limite assintótico.

## Fragmentação

Não existe compactação nem estrutura buddy por ordens.

Alocações unitárias podem criar buracos espalhados. Assim `pmm_free_pages()` pode indicar muitas páginas livres enquanto `pmm_alloc_contig` não encontra um run grande.

O cursor next-fit-like ajuda a distribuir buscas e retorna para endereços liberados menores, porém não elimina fragmentação externa.

Consumers de grandes buffers contíguos precisam aceitar falha ou usar scatter/gather, IOMMU, reservation antecipada ou outra estratégia.

## Self-test

`pmm_selftest` roda no boot logo depois de `pmm_init`.

Ele:

1. aloca três páginas;
2. exige endereços não zero e distintos;
3. converte cada página através do HHDM;
4. escreve uma assinatura de 64 bits diferente em cada uma;
5. lê e compara as assinaturas;
6. libera duas páginas;
7. aloca outra página;
8. exige que ela reutilize um dos dois endereços liberados;
9. imprime contadores;
10. libera as páginas restantes do teste.

Isso valida unicidade básica, acesso de RAM pelo HHDM e reutilização.

O teste não prova:

- comportamento contíguo sob fragmentação;
- máscara DMA32;
- stress concorrente real em várias CPUs;
- detecção de double free;
- overlaps anormais do memory map;
- memória acima do teto de 32 GiB.

Essas propriedades precisam de validação separada caso se tornem claims de release.

## Fronteiras de falha e misuse

As APIs do PMM usam políticas diferentes:

- falta de memória em alloc retorna zero;
- free contíguo com endereço desalinhado/fora do range causa panic;
- `pmm_claim_at` inválido retorna zero;
- double free de bit já zero é ignorado;
- requests DMA32 inválidos falham ou retornam;
- usar HHDM helper antes de bootinfo causa panic.

Portanto não é correto afirmar que “todo erro de PMM resulta em panic”.

O misuse mais perigoso é devolver ao PMM um frame ainda referenciado por page table, DMA ou outra CPU. O bitmap não conhece referências externas. Teardown de memória virtual precisa coordenar TLB shootdown/quarantine antes que a memória física volte a ser reutilizável.

## Segurança e isolamento

Falha no allocator físico atravessa todas as abstrações.

Se um mesmo frame for entregue a dois owners, page table, processo, device ou estrutura de kernel podem corromper uns aos outros. Free prematuro pode virar information leak ou arbitrary corruption quando a página for reutilizada.

O PMM atual garante exclusão mútua e unicidade do bitmap para chamadas válidas, mas não possui owner IDs, reference counting ou zero-on-allocation global.

Camadas superiores zeram páginas quando seu contrato exige. `proc_commit`, por exemplo, limpa a página antes de expô-la ao processo.

Logo “frame alocado” não significa “frame sanitizado para user mode”.

## Limitações atuais

O desenho atual é deliberadamente simples. As principais limitações são:

- teto físico fixo de 32 GiB;
- bitmap fixo de 1 MiB;
- ausência de NUMA;
- ausência de buddy allocator e page caches per-CPU;
- nenhuma compactação física;
- nenhum reference count por frame;
- nenhum metadata de owner/provenance;
- double free não é rejeitado estritamente;
- ausência de zone allocator genérico;
- pool DMA32 dedicado de apenas 64 KiB;
- sem reclaim posterior de bootloader-reclaimable;
- sem zeroing automático de todo frame;
- contiguidade sensível à fragmentação.

Essas características pertencem à implementação atual, não à definição geral de PMM.

## Evolução arquitetural

O allocator pode crescer mantendo o mesmo contrato fundamental de ownership.

Caminhos plausíveis:

- metadata dimensionado à RAM descoberta;
- zones DMA32/normal/high explícitas;
- buddy allocation para runs de potência de dois;
- caches per-CPU para reduzir contenção;
- pools NUMA-local;
- refcounts para páginas compartilhadas;
- provenance/owner em builds de debug;
- page poisoning e políticas de zeroing;
- reclaim de regiões liberáveis quando seu lifetime termina.

Qualquer evolução deve preservar uma regra: frame físico não pode retornar ao pool livre enquanto CPU ou device ainda puder usar uma referência antiga.

## Mapa de fonte

Bitmap, cursor, DMA32, counters, recursão de lock, algoritmos de scan e self-test ficam em `kernel/metal/pmm.c` e `pmm.h`.

`kernel/metal/bootinfo.c`/`bootinfo.h` fornecem memory map do Limine e conversão HHDM.

`kernel/metal/spin.c`/`spin.h` implementam CAS spinlock e save/restore de interrupções usados pelo PMM.

`kernel/metal/heap.c` demonstra enumeração de runs, claim recursivo e a política superior de preservar 32 MiB fora do heap.

As afirmações de implementação foram reconciliadas com a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
