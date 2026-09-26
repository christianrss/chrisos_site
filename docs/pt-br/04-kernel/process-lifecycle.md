---
id: process-lifecycle
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/syscall.c
  - kernel/net/sock.c
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

## Recursos de outros subsistemas

`syscall_close_owner` invalida os descriptors de arquivo do PID.

`sock_close_proc` fecha recursos de socket.

Adicionar novas classes de handles exige incluir cleanup ou evoluir para um mecanismo geral de ownership.

## Destroy do current

O switch para PID0 usa o caminho normal e troca CR3 antes de desmontar mappings.

Na arquitetura BSP-only não há outro CPU executando o mesmo processo. Se isso mudar, teardown precisará provar que nenhum core ainda usa o address space antes de liberar frames/page tables, ligando lifecycle a TLB shootdown e task migration.

## Falhas e limites

Create falha por falta de slot, falha de clone ou falha da stack. Commit falha por PID, capacidade, PMM ou map.

Não há swap/overcommit.

Framebuffer setup pode ter commit parcial antes de uma falha posterior; teardown usa a tabela owned como verdade para liberar o que foi adquirido.

## Segurança

Frames user são zerados. User mappings recebem `MM_USER`. `proc_map_user` rejeita endereço fora do lower canonical half usado pelo projeto.

Destroy fecha resources associados ao PID.

PIDs são índices sem generation tag. Um stale PID guardado após destroy pode apontar para outro processo quando o slot for reutilizado. Callers precisam respeitar lifetime; um future handle model poderia incorporar geração.

## Desempenho

Create procura em 32 slots. Page ownership procura linearmente em no máximo 288 records. Destroy percorre o mesmo limite.

Esses bounds pequenos favorecem clareza. Escalar para milhares de mappings/processos exigiria outras estruturas.

Demand paging reduz alocação eager e aumenta custo de first touch.

## Validação

Testes devem cobrir exaustão dos 31 user slots, unwind de falhas, duplicate map, zero-fill, limites de VM/stack/heap/fb, máximo do heap, panic off-BSP, block/unblock, destroy do current trocando para PID0, retorno exato de frames e cleanup de file/socket.

Um loop create/destroy comparando PMM antes/depois é importante para detectar leaks.

## Limitações atuais

Não há user threads independentes por processo aqui. Current/scheduler state são BSP-only. Capacidades são estáticas. Heap só cresce. Fault history é global. Teardown de resource classes é explícito.

O site deve apresentar esses limites, não esconder atrás de “process management completo”.

## Mapa de fonte

Lifecycle em `kernel/metal/proc.c`/`proc.h`; CR3/mapping em `mm.c`/`mm.h`; frames em `pmm.c`/`pmm.h`; teardown de handles em `syscall.c` e `kernel/net/sock.c`. O Source Atlas publica a íntegra na revisão `da3df29cb397932c43d32373871fb9380e688ade`.
