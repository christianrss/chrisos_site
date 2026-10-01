---
id: clvm-memory
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/clvm/clvm.h
  - compiler/chrisc/chrisc.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - kernel/lang/clvm_sys.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/pmm.h
  - kernel/metal/irq.c
  - tools/test_load64_zero.c
  - tools/test_store64_step.c
  - tools/test_store64_copy.c
  - tools/test_doom_jit_smoke.c
  - tools/test_doom_strinit.c
symbols:
  - clvm_vm_init
  - clvm_vm_set_memory
  - mem_ok
  - clvm_guest_malloc
  - clvm_guest_free
  - clvm_guest_realloc
  - clvm_guest_setjmp
  - clvm_guest_longjmp
  - lang_attach_slot_ram
  - lang_free_slot_ram
  - proc_set_vm
  - proc_vm_ptr
  - proc_commit
  - proc_fault_demand
  - vm_bytes
  - vm_cstr
  - vm_copy_in
  - vm_copy_out
  - clvm_threads_tick
depends_on:
  - chrisc-clvm
  - clvm-bytecode
related:
  - clvm-syscalls
  - clvm-interpreter
  - calling-conventions
  - gc-libraries
  - virtual-memory
  - process-lifecycle
---

# Memória, alocação e isolamento do CLVM

## Escopo

CLVM apresenta uma região plana de guest memory ao bytecode, enquanto ChrisOS pode fornecer backing para essa região de formas diferentes.

No nível da VM, address é integer offset em:

    vm->memory[0 .. vm->mem_size)

No nível do sistema operacional, vm->memory pode apontar para uma allocation do kernel heap ou para um range virtual fixo mapeado no address space de um ChrisOS process.

Essas duas camadas precisam permanecer distintas.

O guest CLVM não recebe arbitrary host pointers para ordinary loads/stores. LOAD, LOADB, LOAD64, FLOAD e seus stores correspondentes interpretam stack values como guest offsets e validam contra mem_size antes de dereference.

O runtime, porém, possui helpers e syscall paths adicionais com regras próprias de validação. O isolamento depende de todos esses caminhos, não apenas do core interpreter.

![Camadas de memória do CLVM](../../assets/diagrams/clvm-memory-pt-br.svg)

## Domínios de address

Vários address domains coexistem no runtime CLVM.

| Domínio | Representação | Significado |
|---|---|---|
| bytecode PC | u32 | offset no CLV code payload |
| guest data pointer | integer VM value | offset a partir de vm->memory |
| vm->memory | host/kernel C pointer | base da guest data region |
| process VM virtual base | 0x02000000 | mapping do processo ChrisOS atual usado pela CLVM RAM |
| kernel heap pointer | native pointer | fallback backing e objetos do kernel |
| JIT native address | native executable address | generated host code, não guest pointer |

Um guest pointer de valor 4096 normalmente significa “byte 4096 dentro da CLVM guest RAM”.

Ele não significa host virtual address 0x1000.

Interpreter converte o offset em host-accessible address somente depois de validar o range:

    host_address = vm->memory + guest_offset

Essa distinção é o principal memory-safety invariant da VM.

## Estado de memória em ClvmVm

ClvmVm armazena:

    uint8_t *memory
    uint64_t mem_size
    uint8_t mem_owned
    uint64_t heap_off

memory é a backing base.

mem_size é o limite lógico do guest address space.

mem_owned indica se o core VM alocou o backing atual e deve liberá-lo quando outro backing for instalado.

heap_off é o cursor atual do bump allocator.

Operand stack, call stack, IL local/argument arrays e TLS são fields do próprio ClvmVm; não ficam dentro da guest data region.

## Inicialização default

clvm_vm_init começa com CLVM_MEMORY_SIZE bytes.

Na revisão documentada:

    CLVM_MEMORY_SIZE = 1 MiB

A allocation depende do build target.

No kernel freestanding do ChrisOS, VM usa kmalloc/kfree.

Em hosted build usa calloc/free.

O build RISC-V usa pool estático de dois megabytes com bump allocation alinhada.

Quando a allocation funciona, clvm_vm_init zera a região de um megabyte, configura mem_owned, grava mem_size e escolhe heap_off inicial.

Esse buffer inicial normalmente é temporário no desktop pipeline porque lang_attach_slot_ram pode substituí-lo por process-backed RAM ou slot RAM alocada separadamente.

## Substituição do backing store

clvm_vm_set_memory instala nova memory base e size.

Se a VM atualmente possui outro backing sob sua ownership, libera o buffer anterior primeiro.

Depois limpa mem_owned, pois o caller passa a ser owner da memória fornecida.

Essa transferência de ownership é importante.

Depois de clvm_vm_set_memory, teardown genérico da VM não pode simplesmente liberar vm->memory. LangSlot ou process que forneceu backing passa a controlar o lifetime.

A função também recalcula heap_off conforme o novo tamanho.

## Heurística de início do heap

O guest allocator atual não recebe o final address real dos static data do ChrisC.

Em vez disso, a VM escolhe heap start pelo tamanho total da memória:

| Tamanho de guest RAM | heap_off |
|---|---:|
| pelo menos 16 MiB | 1 MiB |
| mais de 128 KiB e menos de 16 MiB | 64 KiB |
| 128 KiB ou menos | metade da memória |

O comentário no source explica a motivação: programas do porte de Doom colocam globals e strings bem acima de 64 KiB, então allocator precisa iniciar mais distante do low static data.

Isso é heuristic partition, não linker-defined segment boundary.

Não existe field atual no CLV header dizendo “static data termina no offset X”.

Logo a correção depende de o static-memory footprint do compiler permanecer abaixo do heap start selecionado.

## Layout estático do ChrisC

ChrisC atribui fixed guest offsets a muitos source objects durante compilation.

Compiler inicia mem_next em zero.

À medida que declarations são criadas, storage é atribuído a partir de mem_next e o cursor avança conforme size/alignment.

Depois, chrisc_emit posiciona string pool após os static data acumulados, reserva ordinary-call argument area compartilhada e em seguida varargs area.

Conceitualmente:

    0
    +---------------------------+
    | globals / fixed variables |
    +---------------------------+
    | arrays / structs          |
    +---------------------------+
    | string pool               |
    +---------------------------+
    | icall argument scratch    |
    +---------------------------+
    | varargs scratch           |
    +---------------------------+
    | espaço não reservado      |
    +---------------------------+
    | guest bump heap           |
    +---------------------------+
    | RAM restante              |
    +---------------------------+
    mem_size

O diagrama é conceitual. A VM atual não mantém segment descriptors explícitos para essas regiões.

Vários paths do ChrisC verificam crescimento contra CLVM_MEMORY_SIZE, especialmente aggregates e strings, mas o heap cursor continua sendo escolhido independentemente pelo runtime.

Um static footprint suficientemente grande pode portanto se aproximar ou ultrapassar o heap start heurístico.

## Invariant de bounds check do core

Core interpreter usa mem_ok nas ordinary bytecode memory operations.

A forma importante é:

    se memory é null -> rejeita
    se address < 0 -> rejeita
    se address > mem_size -> rejeita
    se length > mem_size - address -> rejeita
    caso contrário -> válido

A forma com subtração evita overflow em address+length durante validação.

O byte interval válido é:

    address <= x < address + length
    e
    address + length <= mem_size

LOADB/STOREB pedem um byte.

LOAD/FLOAD e STORE/FSTORE pedem quatro.

LOAD64/STORE64 pedem oito.

LDFLD/STFLD validam object address mais field offset para transferência de oito bytes.

Ordinary invalid memory operation muda VM para CLVM_FAULT_BAD_ADDRESS.

## Logical bounds versus physical residency

Em process-backed memory, mem_size descreve o logical CLVM range, mas nem toda page precisa estar resident.

proc_set_vm registra logical vm_bytes e faz commit somente da primeira page.

Quando execução toca posteriormente uma page válida mas ainda não committed, o x86 page-fault path chama proc_fault_demand.

Se fault address estiver em:

    PROC_VM_VIRT <= address < PROC_VM_VIRT + vm_bytes

proc_fault_demand chama proc_commit para aquela page.

proc_commit obtém physical page do PMM, zera, mapeia writable na process page table e registra ownership.

Assim logical CLVM bounds check e CPU demand paging resolvem problemas diferentes:

- CLVM bounds check decide se guest pode endereçar um offset;
- process paging decide se uma physical page já existe para a localização virtual permitida.

## Process virtual base fixo

proc_vm_ptr retorna atualmente:

    PROC_VM_VIRT = 0x02000000

para qualquer process ID.

O pointer value é intencionalmente o mesmo virtual address em page tables diferentes.

Ele só é meaningful enquanto o address space do processo correspondente está ativo.

lang_tick impõe essa disciplina operacional mudando para o process do slot antes de executar clvm_step ou JIT function e retornando a PROC_KERNEL depois.

CLVM child threads registram igualmente o process em que foram criadas; clvm_threads_tick muda para esse process antes de executar child VM.

Kernel code que acessa process-backed vm->memory fora do execution loop precisa manter a mesma context discipline. O checkpoint restore de hot reload muda explicitamente para o process antes de copiar bytes.

## Slot RAM associada a process

O normal desktop launch cria process por proc_create e depois chama lang_attach_slot_ram.

Com process válido, requested guest RAM é:

    max(image.mem_hint, CLVM_MEMORY_SIZE)

proc_set_vm pode reduzir esse request.

O slot registra:

    heap_ram
    heap_ram_sz
    user_ram = 1

e instala process virtual pointer por clvm_vm_set_memory.

Somente a primeira page é explicitamente zerada durante attachment. As later demand-committed pages são zeradas individualmente por proc_commit.

O nome heap_ram é histórico/operacional; no caso process-backed ele aponta para process VM virtual range e não para kernel-heap object.

## Ceiling atual da memória por process

A implementação de process usa:

    PROC_PAGES = 288
    PMM_PAGE   = 4096 bytes

proc_set_vm limita o logical requested VM range a:

    288 * 4096 = 1.179.648 bytes

aproximadamente 1,125 MiB.

Essa é limitação atual importante.

CLV v2 consegue transportar memory hint muito maior, e o compiler pipeline grava atualmente hint de 32 MiB para programas gerados suficientemente grandes.

O process-backed path não consegue honrar hint de 32 MiB nessa revisão porque proc_set_vm o reduz ao ceiling de page accounting do processo.

O mesmo array ProcPage também rastreia outros user mappings owned pelo process, como a user stack inicialmente committed; portanto a quantidade de VM pages que realmente pode se tornar resident pode ser menor que o range teórico de 288 pages antes de a tracking table saturar.

O heap-backed fallback não possui esse limite específico de PROC_PAGES.

## Fallback pelo kernel heap

Se proc_create falha e o slot fica sem process, lang_attach_slot_ram usa kernel heap memory.

Primeiro consulta heap_free_bytes e tenta preservar:

    CLVM_HEAP_RESERVE = 64 MiB

para o restante do kernel.

Requested guest memory continua sendo no mínimo um MiB e pode usar CLV memory hint.

Se request excede capacidade restante e essa capacidade ainda é pelo menos um MiB, request é reduzido para o cap disponível.

A allocation resultante é zerada.

Se a VM já tinha initial memory, runtime copia quantos bytes couberem para o replacement buffer antes de instalá-lo.

Nesse modo, heap_ram é kmalloc allocation real e lang_free_slot_ram a libera com kfree.

## Ownership no teardown

Process-backed e heap-backed RAM têm owners diferentes.

Com user_ram ativo, lang_free_slot_ram apenas limpa pointers/flag do LangSlot. Não libera pages.

proc_destroy chama posteriormente proc_release_user, que unmaps e libera physical pages registradas pelo process.

Sem user_ram, lang_free_slot_ram libera heap_ram diretamente.

Essa divisão evita que teardown normal do slot tente kfree em process virtual memory e depois libere as mesmas PMM pages no teardown do processo.

Owner precisa permanecer inequívoco em todo replacement/reload path.

## Hot reload

lang_hot_reload reinicializa ClvmVm com a nova image e reanexa a slot RAM.

Pode restaurar até 256 bytes de checkpoint explicitamente salvo quando checkpoint range cabe no novo mem_size.

Em process-backed RAM, checkpoint restore muda para o processo antes de dereference de vm->memory.

Hot reload não preserva o guest address space inteiro como semantic snapshot. Ele recria VM execution state e restaura apenas os bytes selecionados.

O ownership path merece regression coverage contínua porque clvm_vm_init pode criar temporariamente um buffer owned de um megabyte antes de slot backing ser reinstalado.

## Representação do guest malloc

clvm_guest_malloc implementa bump allocator.

Para request n:

    need = align_up(n + 8, 8)

Os primeiros oito bytes guardam need.

O pointer devolvido ao guest é:

    p + 8

onde p é o heap_off anterior.

Depois:

    heap_off = p + need

Layout:

    p
    +--------------------+
    | u64 allocation span|
    +--------------------+  <- returned pointer
    | payload            |
    | ...                |
    +--------------------+
    aligned end

Allocator rejeita zero-size requests e requests acima de 2^40 bytes.

Também exige que o novo span inteiro caiba em mem_size.

Allocation é O(1).

## Guest free

clvm_guest_free atualmente é no-op que retorna success.

Não:

- valida allocation provenance;
- adiciona bloco a free list;
- coalesce espaço;
- move heap_off para trás.

Assim guest heap tem crescimento monotônico de high-water mark durante lifetime do VM backing.

Programa pode chamar free com sucesso sem recuperar reusable capacity.

Isso precisa ser considerado ao portar software que depende de uso prolongado de malloc/free.

## Guest realloc

clvm_guest_realloc sempre cria novo bloco primeiro.

Se old pointer é diferente de zero, pelo menos oito e menor que mem_size, lê o header de oito bytes imediatamente anterior ao pointer.

Subtrai header size, limita copy count ao novo requested size e copia bytes para nova allocation.

O custo é O(n).

Porém a implementação atual não prova que o old pointer fornecido é início de allocation criada por clvm_guest_malloc.

Também não limita o derived old payload length contra:

    mem_size - old_pointer

antes da cópia.

Um guest pode portanto fornecer pointer dentro do range, mas sem provenance, cujos bytes anteriores são interpretados como allocation header.

Isso é validation gap real na current memory boundary e deve ser corrigido antes de o guest allocator ser tratado como robusto contra adversarial inputs.

O normal ChrisC malloc/realloc path espera allocator-produced pointers, mas a syscall boundary atual depende desse behavioral contract.

## Formato de setjmp em guest memory

clvm_guest_setjmp serializa control state em guest memory.

O layout atual começa com:

| Offset | Tamanho | Significado |
|---:|---:|---|
| 0 | 4 | bytecode PC |
| 4 | 4 | operand stack depth |
| 8 | 4 | call stack depth |
| 12 | 4 | marker/current format value |
| 16 | sp * 8 | operand stack entries |
| seguinte | csp * 4 | return PCs |

Isso torna nonlocal control state explícito e portável dentro da VM representation.

Snapshot não inclui arbitrary kernel resources, mutex ownership ou file state.

## Gap de range validation em setjmp/longjmp

O setjmp preflight atual verifica:

    addr + 16 + sp*8 + 8 <= mem_size

mas a serialização real escreve csp*4 bytes da call stack, e não oito bytes fixos.

Portanto call stack suficientemente profunda com buffer perto do final da guest RAM pode passar no preflight atual e ainda escrever além do logical guest range.

clvm_guest_longjmp verifica que os primeiros 16 bytes cabem, lê sp/csp e valida esses counts contra CLVM_STACK_MAX/CLVM_CALL_MAX.

Depois não faz preflight completo de:

    16 + sp*8 + csp*4

antes de ler o state serializado.

São isolation gaps concretos da revisão atual.

Devem ser corrigidos antes de setjmp/longjmp serem descritos como fully memory-safe para arbitrary guest-provided buffer addresses.

## Validação de pointers na syscall boundary

Kernel-side CLVM syscalls não podem confiar em guest integers como C pointers.

clvm_sys.c contém helpers específicos de copy/validation.

vm_bytes valida positive buffer length usando a forma segura contra overflow:

    n <= mem_size - address

vm_copy_in valida source range completo do guest antes de copiar para kernel buffer.

vm_copy_out valida destination range completo antes de escrever do kernel buffer.

vm_cstr percorre byte a byte e só retorna success ao encontrar NUL antes do supplied capacity ou mem_size boundary.

A regra de syscall é:

    validar guest offset e extent completo antes de criar host pointer

Nem todo helper do arquivo usa exatamente a mesma string-truncation policy, então cada syscall continua responsável por usar o helper apropriado.

O capítulo de syscall ABI enumera contratos call-specific.

## Core data memory sem segments

Dentro do logical [0, mem_size), CLVM não aplica per-segment permissions.

Não existe guest-memory page attribute dizendo:

- read-only string pool;
- read-only globals;
- somente heap;
- somente stack;
- execute-only region.

Ordinary STORE pode escrever qualquer in-range guest-data offset.

O bytecode code array é separado de vm->memory, então ordinary STORE não reescreve diretamente o loaded CLV code payload por guest data offset.

Mesmo assim, data address space é plano e read/write.

É mais simples que protected segmented VM, porém oferece menos intra-VM fault containment.

## Threads compartilham guest RAM

CLVM child threads são ClvmVm structures separadas.

Child recebe do parent:

    code
    code_size
    memory
    mem_size
    sys
    sys_user
    process identity

Logo child e parent compartilham intencionalmente os mesmos guest-memory bytes.

Não compartilham operand stacks, call stacks ou TLS arrays, pois esses são fields de cada ClvmVm.

O modelo é thread-like:

    shared data address space
    + independent execution stacks/state

Concurrent access à ordinary guest memory exige synchronization.

Mutex/condition syscalls usam guest addresses como localização dos synchronization objects e podem bloquear/acordar child VMs.

## Gap de allocator state nas child threads

O child ClvmVm é inicialmente zerado.

Thread creation copia memory/execution pointers, mas não copia nem inicializa heap_off.

Consequentemente heap_off da child permanece zero.

Se child chamar ordinary guest malloc syscall, clvm_guest_malloc começa allocation no offset zero da mesma memória compartilhada com parent.

Isso pode sobrescrever globals/static data e violar allocator state do parent.

É um current concurrency bug/limitação concreto.

Um shared-heap design correto precisa de uma destas abordagens:

- um allocator cursor/state compartilhado por todas as VMs do process;
- synchronization sobre allocator compartilhado;
- ou per-thread heaps em regiões disjuntas.

O código atual não implementa nenhuma das três para clvm_guest_malloc.

## TLS versus guest memory

Cada ClvmVm possui:

    int64_t tls[16]

Esse array não pertence à shared guest memory.

Como child recebe ClvmVm zerado, começa com TLS entries independentes e zeradas.

Isso fornece pequeno thread-local state domain mesmo com shared data region.

É facility do runtime CLVM, não implementação de ELF TLS ABI.

## Process paging e CLVM faults

Duas classes de fault podem aparecer em torno de memory.

Guest offset rejeitado por mem_ok produz:

    CLVM_FAULT_BAD_ADDRESS

dentro do VM state.

Logical process-backed address válido cuja page não é resident pode causar hardware page fault vector 14.

O interrupt path tenta primeiro proc_fault_demand.

Se address está em allowed process region e page pode ser committed, execution pode continuar.

Se não está em demand range reconhecido ou allocation falha, fault segue para normal process/kernel fault handling.

Portanto nem todo host page fault implica bad CLVM guest offset.

## Semântica de memória no JIT

JIT executa native instructions, mas precisa preservar os mesmos logical guest bounds do interpreter.

Os generated paths usam fields de ClvmVm para memory base, size e fault state e roteiam comportamento não nativo/complexo por helpers.

Memory safety contract é definido em termos de VM-visible behavior, não pelo fato de execução ocorrer no switch-based interpreter ou em generated native code.

Tests que comparam interpreter/JIT são especialmente importantes em LOAD/STORE edge cases, pois missing JIT bound check bypassaria a proteção de mem_ok.

## Memory hints são advisory

CLV v2 possui mem_hint.

Compiler pipeline usa hint de 32 MiB para generated bytecode images suficientemente grandes.

Hint não garante que runtime fornecerá exatamente esse tamanho.

Process policy, PROC_PAGES limits, heap availability e allocation failure podem reduzir ou rejeitar request.

Software deve tratar effective vm->mem_size como runtime capacity em vez de assumir que image hint foi honrado integralmente.

Atualmente não há guest opcode no core VM que consulte diretamente mem_size como parte de standardized portable memory-query ABI; application behavior depende de contracts de nível mais alto.

## Managed GC memory é domínio separado

A CLVM syscall table também expõe gc_alloc.

Na revisão atual, esse path chama kernel/compiler GC allocator e coloca o resulting native pointer value em int64_t.

Esse value não é produzido por clvm_guest_malloc nem é ordinary offset em vm->memory.

Portanto pertence a managed/native address domain diferente.

Ordinary CLVM LOAD/STORE aplica guest-offset bounds e não deve ser assumido capaz de dereference de native GC pointer.

Esse mixed pointer model é uma razão para manter managed library/GC layer explicitamente separada do ordinary CLVM guest heap até existir unified object-reference ABI.

## Performance

Core bounds checks são O(1).

LOAD/STORE transferem no máximo oito bytes na instruction set atual.

Demand paging adia physical allocation e reduz resident memory inicial, mas o first touch custa page fault, PMM allocation, zeroing e page-table update.

clvm_guest_malloc é O(1).

clvm_guest_free é O(1) porque não executa reclamation.

clvm_guest_realloc é O(k), onde k é a quantidade copiada.

Process page ownership lookup em proc_commit percorre o process page array, portanto é linear no número de pages já tracked.

O scan é bounded por PROC_PAGES, mas não é assintoticamente constante.

## Cache e localidade

Guest address space é logicamente contíguo, fornecendo conventional spatial locality para arrays/structures ChrisC.

Bump allocation coloca allocations sucessivas próximas.

Process-backed physical pages não precisam ser fisicamente contíguas; virtual contiguity esconde isso do CLVM.

Operand/call stacks separadas ficam dentro de ClvmVm como small fixed arrays, geralmente com boa locality para interpreter state.

Child VMs compartilham data pages; concurrent writes nas mesmas guest locations podem gerar normal cache-coherence traffic em SMP mesmo que a VM abstraction seja de alto nível.

## Failure modes

Principais failure modes:

| Falha | Resultado |
|---|---|
| initial one-megabyte VM allocation falha | memory = null, mem_size = 0 |
| slot backing allocation falha | application launch falha |
| guest LOAD/STORE fora do range | CLVM_FAULT_BAD_ADDRESS |
| guest malloc excede remaining region | failure/zero pela syscall |
| process demand page não pode ser committed | page fault não é resolvido |
| process page tracking enche | novos proc_commit falham |
| free chamado | success sem reclamation |
| invalid realloc provenance | validação insuficiente atualmente |
| setjmp/longjmp perto do fim | total-range checks incompletos |
| child thread malloc | child heap_off atual é inseguro |

Essas falhas pertencem a layers diferentes e devem ser diagnosticadas onde se originam.

## Modelo de segurança e isolamento

O isolation model implementado é composto por layers:

1. bytecode usa guest offsets em vez de arbitrary direct host pointers;
2. core memory instructions aplicam logical mem_size bounds;
3. process-backed execution usa process page tables separadas;
4. uncommitted valid pages são demand allocated;
5. syscalls devem validar guest ranges antes de copiar;
6. privileged hardware syscalls possuem capability checks separados;
7. slot/process teardown mantém ownership e libera backing resources.

Isso constitui isolamento real, mas ainda não é formally verified sandbox.

Os gaps de realloc e setjmp/longjmp mostram por que todos os alternate memory paths importam.

O bug de allocator state da child também permite corrupção de shared guest address space sem ultrapassar o outer mem_size bound.

Claims de segurança devem ser específicos: ordinary interpreter memory operations têm range checks; o complete CLVM runtime ainda possui known validation/ownership gaps.

## Evidência de validação

tools/test_load64_zero.c instala backing de 32 MiB e exercita 64-bit load no JIT path.

tools/test_store64_step.c e tools/test_store64_copy.c exercitam 64-bit writes e copy-sensitive behavior com guest-memory region maior.

tools/test_doom_jit_smoke.c e testes diagnósticos relacionados aumentam VM memory para 32 MiB em hosted test configurations e exercitam large-program execution.

tools/test_doom_strinit.c reporta heap_off e executa initialization com backing ampliado, fornecendo evidência da policy de 1 MiB para heap start em large memory.

Suites mais amplas de ChrisC/JIT exercitam muitos generated guest loads/stores.

O source também possui bounds checks explícitos passíveis de audit determinístico.

Na revisão atual, não aparecem no inspected test set regressions adversariais dedicados a invalid realloc provenance, near-end setjmp buffers e child-thread malloc state. Esses casos devem ser adicionados.

## Limitações atuais

Na revisão documentada:

- guest memory é uma única flat read/write data region;
- heap/static separation é heurística e não deriva de explicit final static-data boundary;
- process-backed VM request é limitado por PROC_PAGES a aproximadamente 1,125 MiB com as constants atuais;
- large 32 MiB CLV memory hints não são honrados pelo normal process-backed path;
- process page tracking table é compartilhada com outros owned user mappings e pode saturar;
- guest free não recupera memória;
- guest realloc não valida allocation provenance nem limita old copy length ao guest range restante;
- setjmp não preflighta complete call-stack serialization size;
- longjmp não preflighta complete serialized state antes de restore;
- child CLVM VMs compartilham memory, mas não herdam/compartilham heap_off;
- guest allocator não é synchronized para multi-thread use;
- per-region read/write permissions não existem dentro de vm->memory;
- native GC pointers e guest offsets coexistem atualmente como pointer domains diferentes;
- memory hints são advisory, não guaranteed capacity;
- fallback/hot-reload ownership paths dependem de coordenação correta entre mem_owned e user_ram.

## Fronteira de roadmap

Uma CLVM memory architecture mais forte pode introduzir:

- explicit image/static-data-end field para iniciar heap com segurança;
- reclaiming allocator com validated block metadata;
- allocation provenance/canaries ou compact allocation table;
- allocator state único e synchronized compartilhado por CLVM threads;
- region descriptors com read/write permissions;
- guard pages ao redor de guest-memory mappings;
- process page accounting maior ou dynamic page-owner structure;
- runtime query para effective memory size;
- complete setjmp/longjmp range preflight;
- bytecode verifier que raciocine sobre pointer-producing operations;
- unified managed object-reference representation que nunca exponha raw kernel pointers.

São mudanças futuras até existirem source e tests correspondentes.

## Mapa de source e revisão

Core VM memory state, bounds checking, heap allocation e setjmp/longjmp estão em compiler/clvm/clvm_vm.c e declarados em compiler/clvm/clvm_vm.h.

ChrisC static guest-address assignment, string placement e call scratch regions ficam em compiler/chrisc/chrisc.c.

Slot memory selection, process-context switching, fallback backing, hot reload e teardown ficam em compiler/lang_pipeline.c.

Syscall-side guest buffer validation e CLVM thread creation ficam em kernel/lang/clvm_sys.c.

Process virtual-memory mapping e demand commitment estão em kernel/metal/proc.c, com page-fault dispatch em kernel/metal/irq.c.

Todas as afirmações de comportamento atual deste capítulo foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
