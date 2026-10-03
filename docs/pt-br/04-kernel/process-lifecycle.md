---
id: process-lifecycle
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/syscall.c
  - kernel/net/sock.c
  - kernel/metal/irq.c
  - tools/test_pmm_cycle.c
symbols:
  - proc_init
  - proc_create
  - proc_destroy
  - proc_switch
  - proc_commit
  - proc_release_user
  - proc_block
  - proc_unblock
  - proc_fault_demand
  - proc_set_vm
  - proc_sbrk
  - proc_fb_ptr
  - mm_free_user_space
depends_on:
  - virtual-memory
  - physical-memory
  - user-mode-entry
related:
  - user-copy
  - processes-syscalls
  - page-faults
---

# Ciclo de vida e estado de processos

## Escopo

O gerenciamento de processos atual é limitado e explícito. Existem no máximo 32 slots; o slot zero representa o kernel. Um processo user possui raiz de page tables, tabela limitada de páginas de sua propriedade, metadados das regiões virtuais, estado simples e nome curto. Troca de processo user ocorre somente no BSP.

Isso não é um scheduler maduro com várias threads por processo e run queues por CPU. Ainda assim existe lifecycle real: criação aloca address space e stack inicial, mapping transfere ownership de frames, page fault pode materializar memória, block altera runnability e destroy libera páginas, page tables e recursos.

## Tabela de processos

`g_proc[PROC_MAX]` é array estático com 32 entradas.

`Proc` guarda:
- used;
- alive;
- state;
- cr3;
- vm_bytes;
- heap_brk;
- npages;
- fb_pages;
- nome de 24 bytes;
- até 288 pares virtual/físico em `ProcPage`.

A lista de ownership é essencial para teardown. Um PTE dizer “há um frame mapeado” não informa, sozinho, se aquele frame deve ser devolvido pelo processo.

## Estados

O header define FREE, READY, BLOCK_SOCK, BLOCK_JOIN e BLOCK_IRQ.

`proc_runnable` exige slot válido, alive e READY.

Não há zombie, stop/continue, prioridade ou estado por thread nessa estrutura.

## Transições de estado

O modelo pode ser descrito por um conjunto pequeno de transições:

| Origem | Operação/evento | Destino |
|---|---|---|
| FREE | `proc_create` concluído | READY |
| READY | `proc_block(pid, reason)` | BLOCK_SOCK / BLOCK_JOIN / BLOCK_IRQ |
| bloqueado | `proc_unblock` ou `proc_unblock_why` correspondente | READY |
| qualquer estado user vivo | fault fatal | `alive = 0`, seguido de teardown |
| qualquer slot user usado | `proc_destroy` | FREE |

`alive` e `state` são campos distintos. `proc_runnable` exige simultaneamente `alive != 0` e `state == READY`. Assim, `proc_record_fault` pode tornar o processo não executável antes de `proc_destroy` liberar definitivamente o slot. Callers não devem inferir liveness apenas pelo valor de `state`.

## Inicialização

`proc_init` limpa todos os slots, reseta heap break e page counts.

Depois configura PID0:
- used/alive;
- READY;
- CR3 = `mm_kernel_cr3()`;
- nome “kernel”.

`g_current` passa a zero e slice/fault record são limpos.

O kernel participa do namespace de PID/current, mas não do ownership de páginas user.

## Criação

`proc_create` procura slot 1–31 livre. Chama `mm_clone_kernel_space`; zero significa falha.

Inicializa o slot e chama `proc_commit(pid, PROC_STACK_VIRT)`.

Se a stack inicial não puder ser materializada, `proc_destroy` desfaz o processo.

PID retornado com sucesso já tem CR3 próprio e primeira página de stack.

## Mapeamentos do kernel

O processo recebe um address space derivado de `mm_clone_kernel_space`. A topologia exata pertence ao capítulo de memória, mas o conceito é importante: user CR3 pode conter mappings supervisor necessários ao kernel; isolamento vem dos flags de página/CPL.

O objeto Proc apenas guarda CR3.

## Layout virtual

| Uso | Base |
|---|---:|
| VM | `0x02000000` |
| heap | `0x04000000` |
| framebuffer | `0x06000000` |
| stack | `0x07F00000` |
| library | `0x08000000` |

`PROC_PAGES = 288` limita ownership. Heap fica limitado a 256 KiB acima de sua base.

São limites do projeto atual, não limites x86.

## Mapping e ownership

`proc_map_user` valida PID/lower-half e chama `mm_map_cr3` acrescentando `MM_USER`.

`proc_map_owned` alinha VA, recusa duplicate e overflow da tabela, mapeia e grava o par virt/phys.

Se a transferência para ownership falha, caller ainda é responsável por `pmm_free` daquele frame.

Esse contrato evita ambiguidades sobre quem libera memória.

## Commit de página

`proc_commit`:
1. alinha VA;
2. considera página já owned como sucesso;
3. testa capacidade;
4. chama `pmm_alloc`;
5. zera 4 KiB;
6. mapeia Present/Write/User;
7. registra ownership;
8. flush TLB se processo é current.

Zero-fill impede vazar dados de dono anterior do frame.

Falha de mapping devolve o frame a PMM.

## Regiões demand-paged

`proc_set_vm` limita bytes à capacidade e comita primeira página.

`proc_fault_demand` reconhece:
- VM até vm_bytes;
- quatro páginas de stack;
- heap abaixo de heap_brk;
- framebuffer dentro de fb_pages.

Acesso nessas regiões pode chamar `proc_commit` e recuperar o #PF.

Fora delas, fault não é considerado demanda válida.

## Heap

`proc_sbrk` retorna break antigo e cresce até 256 KiB. Não aceita shrink pela API unsigned.

Não comita tudo imediatamente; first touch pode gerar #PF e commit lazy.

## Framebuffer de processo

`proc_fb_ptr` limita a 16 páginas, grava count e comita cada página na base fixa.

É buffer de processo, não mapeamento direto do framebuffer físico/GPU. Essa diferença importa para segurança e ownership.

## Switch

`proc_switch` exige `smp_current_cpu() == 0`. AP provoca panic.

Para PID válido, define `g_current` e executa `mm_switch(cr3)`.

O próprio comentário explica: scheduler state é global e não é seguro em AP.

Logo, paralelismo de jobs não implica paralelismo de processos user.

## Slice de timer

`proc_on_tick` define `g_slice = 1`. Due lê, ack limpa.

Não existe nesse arquivo uma troca preemptiva completa de contexto. É um sinal para scheduling diferido.

## Blocking

`proc_block` coloca um reason. `proc_unblock` retorna READY. `proc_unblock_why` varre todos e acorda processos com o mesmo reason.

Não há waiter list por objeto no process table.

## Fault record

`proc_record_fault` escreve um único `ProcFault` global com PID/TID/CR2/RIP, marca alive=0 e loga.

`proc_last_fault` expõe o último registro.

Não é histórico; próximo fault sobrescreve.

## Destroy

`proc_destroy` recusa PID0.

Se PID é current, troca primeiro para kernel. Isso é obrigatório: page tables ativas não podem ser liberadas enquanto ainda são CR3 corrente.

Depois:
1. libera páginas user;
2. libera user-space page tables se distintas do kernel;
3. fecha file descriptors do PID;
4. fecha sockets;
5. marca slot FREE/dead e zera CR3.

A ordem faz teardown do address space antes de tornar o slot reutilizável.

## Release de páginas

`proc_release_user` percorre cada record. Se phys != 0:
- unmap do CR3;
- `pmm_free`;
- zera registro.

No final zera count, vm_bytes, fb_pages e reseta heap break.

Duplicate ownership é evitado na entrada, reduzindo double free.

## Teardown em duas camadas: frames e page tables

A destruição separa duas classes de ownership.

`proc_release_user` é responsável pelos leaf frames registrados em `ProcPage[]`. Para cada entrada ele remove o mapping virtual e devolve o frame físico à PMM. Somente depois `mm_free_user_space` percorre a metade user da PML4 — entradas 0 a 255 — e libera recursivamente as páginas intermediárias das page tables e a própria PML4 do processo.

O contrato em `mm.h` é explícito: `mm_free_user_space` não libera leaf frames; eles continuam sendo responsabilidade da lista de páginas do processo. Essa divisão evita double free e também evita desmontar as estruturas de tradução antes de `proc_release_user` terminar os unmaps.

A metade kernel da PML4 não é liberada recursivamente no teardown user porque representa mappings compartilhados do contexto privilegiado, não páginas de dados pertencentes ao processo.

## Recursos de outros subsistemas

`syscall_close_owner` invalida os descriptors de arquivo do PID.

`sock_close_proc` fecha recursos de socket.

Adicionar novas classes de handles exige incluir cleanup ou evoluir para um mecanismo geral de ownership.

## Destroy do current

O switch para PID0 usa o caminho normal e troca CR3 antes de desmontar mappings.

Na arquitetura BSP-only não há outro CPU executando o mesmo processo. Se isso mudar, teardown precisará provar que nenhum core ainda usa o address space antes de liberar frames/page tables, ligando lifecycle a TLB shootdown e task migration.

## Capacidade compartilhada e falhas parciais

As 288 entradas de `ProcPage[]` são um limite global por processo, compartilhado entre VM, stack, heap e framebuffer. Os limites de cada região não constituem reservas independentes.

`proc_set_vm` pode limitar `vm_bytes` a `PROC_PAGES * 4096`, mas o processo já possui pelo menos a página inicial de stack. Portanto, pedir o máximo nominal de VM não significa que todas as 288 páginas de VM possam ser materializadas: a mesma tabela também precisa representar stack e qualquer heap/framebuffer já comitado.

Há ainda semânticas de falha parcial. `proc_set_vm` grava `vm_bytes` antes de tentar o primeiro commit; se `proc_commit` falhar, a função retorna zero mas a faixa declarada permanece no objeto. `proc_fb_ptr` grava `fb_pages` antes do loop de commits; uma falha no meio pode deixar algumas páginas já materializadas. Isso não causa leak por si só porque as páginas adquiridas entraram na tabela de ownership e serão liberadas por `proc_destroy`, mas callers devem considerar a operação falha apesar do estado parcial.

`proc_sbrk` é grow-only e compara `old + inc` com o teto de 256 KiB. A implementação atual não faz uma checagem separada de overflow unsigned antes dessa soma. Um incremento artificialmente enorme pode causar wraparound e é uma borda que precisa de teste/hardening antes de tratar a API como robusta contra entrada hostil.

## Falhas e limites

Create falha por falta de slot, falha de clone ou falha da stack. Commit falha por PID, capacidade, PMM ou map.

Não há swap/overcommit.

Framebuffer setup pode ter commit parcial antes de uma falha posterior; teardown usa a tabela owned como verdade para liberar o que foi adquirido.

## Segurança

Frames user são zerados. User mappings recebem `MM_USER`. `proc_map_user` rejeita endereço fora do lower canonical half usado pelo projeto.

Destroy fecha resources associados ao PID.

PIDs são índices sem generation tag. Um stale PID guardado após destroy pode apontar para outro processo quando o slot for reutilizado. Callers precisam respeitar lifetime; um future handle model poderia incorporar geração.

## Custos algorítmicos

| Operação | Estrutura | Custo |
|---|---|---|
| encontrar PID livre | scan de slots 1–31 | `O(PROC_MAX)` |
| testar página owned | scan de `ProcPage[]` | `O(npages)` |
| commit de página | busca de duplicate + PMM/map | `O(npages)` mais MM/PMM |
| `proc_unblock_why` | scan de todos os PIDs user | `O(PROC_MAX)` |
| release de páginas | percorre páginas owned | `O(npages)` mais unmap/free |
| destroy | release + page tables + resources | proporcional aos recursos possuídos |

Com apenas 31 PIDs user e 288 records de páginas, scans lineares são previsíveis e fáceis de auditar. Eles deixam de ser apropriados se o projeto crescer para milhares de mappings, threads e processos.

## Desempenho

Create procura em 32 slots. Page ownership procura linearmente em no máximo 288 records. Destroy percorre o mesmo limite.

Esses bounds pequenos favorecem clareza. Escalar para milhares de mappings/processos exigiria outras estruturas.

Demand paging reduz alocação eager e aumenta custo de first touch.

## Evidência executável e lacunas

`tools/test_pmm_cycle.c` testa a camada inferior de memória física com 1.000 alocações e liberações. O teste confirma que `pmm_free_pages()` cai exatamente pelo número alocado e volta ao valor inicial depois do ciclo, além de verificar a identidade entre páginas usadas, livres e utilizáveis.

Isso é evidência útil para a primitiva usada por `proc_commit` e `proc_release_user`, mas não é um teste de lifecycle de processos. Ele não cria um `Proc` real, não clona CR3, não executa `proc_destroy`, não verifica cleanup de fd/socket e não demonstra que leaf frames e page-table pages são liberados exatamente uma vez.

Ainda falta, portanto, um gate específico de create/destroy que compare contadores da PMM antes/depois, force falhas intermediárias e valide reutilização segura do PID.

## Validação

Testes devem cobrir exaustão dos 31 user slots, unwind de falhas, duplicate map, zero-fill, limites de VM/stack/heap/fb, máximo do heap, panic off-BSP, block/unblock, destroy do current trocando para PID0, retorno exato de frames e cleanup de file/socket.

Um loop create/destroy comparando PMM antes/depois é importante para detectar leaks.

## Invariantes de teardown

A correção do destroy depende desta ordem:

1. se o PID é current, selecionar PID0 e trocar CR3;
2. unmapear e liberar os leaf frames pertencentes ao processo;
3. liberar estruturas de page table do user half;
4. fechar descritores e sockets indexados pelo PID;
5. somente então marcar o slot como FREE e limpar CR3.

Tornar o slot reutilizável antes das etapas 2–4 permitiria que um novo processo com o mesmo PID observasse recursos antigos. Liberar CR3/page tables antes de sair do address space atual poderia desmontar a tradução usada pelo próprio teardown. A ordem do código é, portanto, parte do contrato de lifetime.

## Limitações atuais

Não há user threads independentes por processo aqui. Current/scheduler state são BSP-only. Capacidades são estáticas. Heap só cresce. Fault history é global. Teardown de resource classes é explícito.

O site deve apresentar esses limites, não esconder atrás de “process management completo”.

## Reconciliação de revisão

Os arquivos de lifecycle, MM, PMM e cleanup descritos aqui não mudaram entre a revisão anteriormente registrada e `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. O avanço de `reviewed_revision` reflete reconciliação de fonte, não a suposição de uma nova capacidade de processos.

## Mapa de fonte

Lifecycle em `kernel/metal/proc.c`/`proc.h`; CR3/mapping em `mm.c`/`mm.h`; frames em `pmm.c`/`pmm.h`; teardown de handles em `syscall.c` e `kernel/net/sock.c`. O Source Atlas publica a íntegra na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
