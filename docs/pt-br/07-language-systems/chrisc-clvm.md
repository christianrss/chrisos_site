---
id: chrisc-clvm
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_format.c
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/lang_pipeline.h
  - compiler/lang_pipeline.c
  - compiler/jit/jit_compile.c
  - compiler/jit/jit_runtime.c
  - kernel/lang/clvm_sys.h
  - kernel/lang/clvm_sys.c
  - tools/test_chrisc_c17.c
  - tools/test_chrisc_fn.c
  - tools/test_chrisc_doom.c
  - tools/test_chrisc_ptr_float.c
  - tools/test_fuzz_clvm.c
  - tools/test_jit_vm.c
  - tools/test_jit_native.c
  - tools/test_editor_vi.c
symbols:
  - chrisc_compile_ex
  - chrisc_compile_files_ex
  - chrisc_emit
  - ClvmImage
  - clvm_parse
  - clvm_write_image
  - clvm_write_image_v2
  - ClvmVm
  - clvm_vm_init
  - clvm_vm_set_memory
  - clvm_step
  - clvm_guest_malloc
  - clvm_guest_realloc
  - lang_run_internal
  - lang_attach_slot_ram
  - lang_tick
  - lang_kill
  - clvm_sys_dispatch
  - clvm_sys_close_slot
  - clvm_threads_tick
depends_on:
  - compiler-pipeline
  - intermediate-representation
  - calling-conventions
related:
  - clvm-bytecode
  - clvm-memory
  - clvm-syscalls
  - clvm-interpreter
  - jit
  - debugger
  - gc-libraries
---

# ChrisC e o modelo de execução CLVM

## Escopo

ChrisC é uma linguagem-fonte do subsistema de linguagens do ChrisOS. Seu principal caminho de aplicações não produz os mesmos objects ChrisO/ELF nativos do KCC. ChrisC é compilado para bytecode CLVM, empacotado em uma imagem CLV e executado por runtime de VM que pode interpretar o bytecode ou traduzir instructions suportadas pelo JIT do CLVM.

O caminho ativo completo é:

    source ChrisC
        ->
    preprocessing / parsing / semantic analysis
        ->
    representação Node[] do ChrisC
        ->
    bytecode CLVM
        ->
    imagem CLV
        ->
    validação da imagem
        ->
    instância runtime LangSlot
        ->
    interpreter ou JIT
        ->
    bridge de syscalls CLVM
        ->
    serviços do kernel e recursos do slot

Essa arquitetura cria execution contract independente da calling convention nativa do KCC e do raw x86-64 instruction encoding.

![Caminho de execução ChrisC e CLVM](../../assets/diagrams/chrisc-clvm-pt-br.svg)

## Por que existe um target de máquina virtual

Um VM target separa o language front end da ISA do processador host.

ChrisC precisa fazer lowering apenas para o CLVM instruction set. O runtime escolhe depois como executar essas instructions.

Esse design fornece:

- um único compiler target para interpretation e JIT;
- guest-memory addressing explícito em vez de source-level host pointers diretos;
- syscall gateway controlado;
- instruction set compacto testável independentemente;
- source maps e debugger integration em torno de bytecode PCs;
- execution model utilizável pelo language environment dentro do próprio sistema;
- caminho para self-hosted compilation sem exigir que ChrisC produza x86-64 diretamente.

O custo é transformar a própria VM em compatibility boundary. Interpreter, JIT, bytecode format, compiler lowering e syscall bridge precisam manter semântica equivalente.

## Fronteira de compilation

ChrisC compilation é implementada principalmente em compiler/chrisc/chrisc.c.

O front end expande source, executa lexing, faz parsing de declarations/functions, mantém semantic bookkeeping e constrói a representação fixa Node[] descrita nos capítulos de compiladores.

chrisc_emit reduz o programa resultante para um byte buffer de CLVM opcodes.

ChrisResult registra, entre outros dados:

- bytecode size;
- entry PC;
- diagnostics;
- source-map information.

O language pipeline chama chrisc_compile_files_ex em compilation multi-file e pode instalar yield callback por chrisc_set_yield. No caminho de compilation dentro do kernel, esse callback periodicamente chama gc_poll e produz progress heartbeat, evitando tratar compilação longa como operação completamente opaca.

## Empacotamento CLV

Raw bytecode normalmente não é o file representation final.

compiler/clvm/clvm_format.c envolve o code em CLV image com header e checksum.

Duas versions são aceitas atualmente.

Version 1 usa header de 16 bytes e entry field de 16 bits.

Version 2 usa header de 24 bytes, entry field de 32 bits e memory hint de 32 bits.

Os logical fields comuns são:

| Campo | Significado |
|---|---|
| magic | ASCII CLVM |
| version | versão do image format |
| flags | image flags conhecidas |
| code size | tamanho do bytecode payload |
| checksum | FNV-1a sobre o bytecode |
| entry | bytecode PC inicial |
| memory hint | tamanho de guest memory solicitado em v2 |
| code | CLVM instruction bytes |

CLVM_MAX_CODE limita o bytecode atualmente a 16 MiB.

O layout detalhado e opcode encoding pertencem ao capítulo dedicado a CLVM bytecode; o ponto arquitetural aqui é que runtime consome validated image, não confia em arbitrary byte buffer.

## Seleção da imagem durante compilation

emit_game_clv escolhe o image version conforme os requisitos do programa gerado.

Programa pequeno cujo code e entry cabem nos limites v1 pode usar o writer v1.

Se code size ou entry ultrapassa 65535, o pipeline escolhe v2.

O pipeline atual também atribui memory hint de 32 MiB a imagens suficientemente grandes, especificamente quando code size ultrapassa 200000 bytes.

A heurística existe para workloads grandes, como programas CLVM do porte de Doom, cujo guest heap e static state ultrapassam o default de um megabyte.

O arquivo CLV resultante é gravado no filesystem do ChrisOS junto com source-map output.

## Validação do loader

clvm_parse executa structural validation antes da execução.

Ele rejeita:

- null arguments;
- arquivos menores que o header necessário;
- magic incorreto;
- versions não suportadas;
- flags desconhecidas;
- code size zero, excessivo ou inconsistente com o arquivo;
- entry point fora do code payload;
- checksum incorreto.

O parser também verifica que code payload ocupa exatamente os bytes posteriores ao header selecionado.

O checksum é FNV-1a do bytecode.

Isso detecta corrupção; não é mecanismo criptográfico de autenticidade. Quem consegue alterar deliberadamente code e checksum consegue criar outra imagem válida.

Execute permission é tratada separadamente pelo runtime quando ChrisFS permission metadata está disponível.

## Ownership runtime: LangSlot

Uma aplicação em execução é representada por LangSlot em compiler/lang_pipeline.c.

O slot possui ou referencia o runtime state necessário para executar e exibir uma language application, incluindo:

- loaded CLV file buffer;
- estado ClvmVm;
- application name;
- VM memory e size;
- process association;
- graphics context e viewport state;
- JIT buffer e function pointer;
- debugger state e breakpoints;
- source-map tables;
- event queues;
- checkpoint data;
- task/window association;
- capability bits;
- teardown state.

Essa estrutura é o operational owner do application lifecycle.

A VM, portanto, não é apenas um objeto ClvmVm isolado. Desktop execution real integra a VM com graphics, process bookkeeping, debugger state, scheduling e kernel resources por slot.

## Sequência de launch

lang_run_internal executa o principal launch path.

A sequência aproximada é:

1. detectar aplicação de mesmo nome já ativa e elevá-la em vez de criar outra instance;
2. localizar language slot livre;
3. alocar file buffer se o slot ainda não possui um;
4. ler o arquivo CLV;
5. aplicar execute permission quando o active filesystem fornece esse check;
6. fazer parse e validar a CLV image;
7. criar/preparar application viewport;
8. inicializar ClvmVm;
9. criar process record associado quando possível;
10. anexar guest RAM;
11. carregar source map;
12. tentar JIT compilation quando policy permite;
13. inicializar debugger/runtime flags;
14. abrir application window;
15. marcar slot como ativo.

Falha em file loading, image parsing, viewport ou guest-memory setup impede a criação de live slot.

## Estado inicial da VM

clvm_vm_init inicializa execution machine a partir de ClvmImage.

O estado inicial inclui:

    pc  = image.entry
    sp  = 0
    csp = 0
    state = CLVM_READY

Ele instala syscall callback e user context, limpa fault state, zera IL local/argument arrays e inicializa TLS entries.

A VM inicialmente aloca CLVM_MEMORY_SIZE, atualmente 1 MiB.

No desktop pipeline, essa memória inicial pode ser substituída pelo backing selecionado para o slot.

## Operand e return stacks

CLVM possui bounded operand stack:

    int64_t stack[256]

e uma return-PC stack separada:

    uint32_t calls[64]

Operand stack transporta arithmetic values, pointers representados como guest offsets, syscall arguments e function results.

Call stack guarda bytecode return PCs.

Isso não é native x86 stack frame.

Como documentado em calling-conventions, ordinary ChrisC formal parameters e locals ficam em guest memory, enquanto CLVM calls preservam control-flow return state separadamente.

Stack overflow/underflow tornam-se VM faults em vez de unchecked host-memory writes.

## Guest memory model

Um CLVM address é interpretado como offset em vm->memory.

O core VM valida ranges por mem_ok antes de load/store.

O check exige:

- memory pointer válido;
- address não negativo;
- address não além de mem_size;
- requested length não maior que o range restante.

O syscall bridge usa checks equivalentes por helpers como vm_bytes, vm_cstr, vm_copy_in e vm_copy_out.

Esse é um invariant central: guest offsets precisam ser validados antes de se tornarem host pointers.

O memory model completo aparece no capítulo clvm-memory.

## Memória associada a process

O desktop language pipeline pode associar slot a ChrisOS process record.

Nesse caso, lang_attach_slot_ram solicita por proc_set_vm uma VM region dimensionada pelo CLV memory hint ou pelo default de um MiB, o que for maior.

Obtém mapped VM pointer por proc_vm_ptr, marca o slot como user-backed RAM, muda para o process context para inicializar memory e então anexa a região ao ClvmVm por clvm_vm_set_memory.

CLS library mappings também podem ser instalados no process.

Essa process association não deve ser confundida com o CLVM guest address space. CLVM code continua usando guest offsets e interpreter/syscall bridge mantêm VM-specific memory semantics.

## Fallback de memory no heap

Se não existe process-backed region, o language pipeline pode alocar VM RAM no kernel heap.

Ele mantém reserva de segurança de 64 MiB do host heap ao dimensionar a allocation.

O requested size começa pelo image memory hint ou default CLVM size, nunca fica abaixo do default de um MiB e pode ser limitado pela heap capacity disponível.

Existing initial VM bytes são copiados para a replacement allocation antes de clvm_vm_set_memory instalá-la.

O slot registra se backing memory pertence ao process ou ao heap para teardown não liberar owner incorreto.

## Guest heap allocator

ClvmVm possui bump-pointer allocator simples usado pelos guest allocation services.

clvm_guest_malloc:

1. rejeita sizes inválidos ou extremos;
2. adiciona allocation header de oito bytes;
3. arredonda o total para alignment de oito bytes;
4. verifica se nova allocation cabe em mem_size;
5. grava allocated span no header;
6. avança heap_off;
7. retorna address imediatamente posterior ao header.

A allocation é O(1).

clvm_guest_free atualmente não recupera space; retorna success sem mover heap_off ou manter free list.

clvm_guest_realloc cria novo bloco e copia o previous payload até o menor tamanho relevante, então o copy cost é O(n).

É mecanismo simples funcional, mas freed space não é reutilizado e effective guest capacity é consumida monotonicamente.

## Ponto inicial do heap

O heap não começa sempre no mesmo fixed address.

clvm_vm_set_memory escolhe heap_off conforme total memory size.

Com pelo menos 16 MiB, heap_off inicia em 1 MiB.

Acima de 128 KiB e abaixo desse threshold, inicia em 64 KiB.

Em espaços menores começa na metade da memory.

A razão explícita no source é manter bump allocator distante de static/global/string data usada por aplicações grandes.

Continua sendo heuristic memory partition, não dynamic layout descrito por linker.

## Interpreter execution

clvm_step executa no máximo o supplied instruction budget.

Para cada instruction:

1. registra opcode PC;
2. bounds-check do opcode fetch;
3. avança program counter;
4. incrementa executed counter;
5. decodifica e aplica opcode semantics;
6. retorna antecipadamente em HALT, WAIT, fault ou scheduler yield.

O custo é O(budget) para opcodes comuns de tempo constante, excluindo syscalls e operações cujo custo depende de data copy.

A VM state machine inclui READY, RUNNING, WAITING, HALTED e FAULTED.

WAITING VMs cedem execução até clvm_vm_wake observar a wake condition.

No freestanding runtime, interpreter também pode yield quando o process scheduler indica fim de slice.

## Interpreter faults

Falhas são armazenadas em ClvmVm em vez de retornarem como host exceptions não estruturadas.

Categorias incluem:

- program counter fora do code;
- unknown opcode;
- truncated instruction operand;
- operand-stack underflow/overflow;
- call-stack underflow/overflow;
- division by zero;
- signed division overflow;
- guest-memory address inválido;
- jump target inválido;
- syscall rejeitada.

fail registra fault code/fault PC e muda VM para CLVM_FAULTED.

Depois disso, clvm_step retorna imediatamente fault nas chamadas seguintes.

## Runtime scheduling

lang_tick integra language slots ativos ao desktop/runtime loop.

Primeiro avança supporting services, incluindo CLVM child threads, e então percorre slots em round-robin.

Slot pode ser pulado se estiver:

- em destruction;
- paused pelo debugger;
- blocked/non-runnable por seu process associado.

Runtime acorda timed waits, entra no process context quando aplicável, executa quantidade bounded de VM work e retorna ao kernel process context.

Slots grandes classificados como game recebem slice policy diferente de pequenos UI slots.

É bounded cooperative execution integrada ao scheduling mais amplo do ChrisOS, não run-to-completion sem limite.

## Interpreter versus JIT

Launch normal de desktop CLV tenta JIT quando debugging não está ativo e JIT não foi globalmente desabilitado.

jit_compile_image é chamado após parse da image e preparação do VM memory.

Se JIT compilation falha no launch, runtime registra falha e usa interpreter.

Debugger usa interpreter intencionalmente para manter bytecode PCs e one-instruction stepping diretamente controláveis.

Depois que aplicação grande já está rodando em JIT, runtime fault inesperado não é tratado como ponto seguro para reiniciar transparentemente no interpreter, pois execution state pode já ter sido parcialmente alterado.

O capítulo JIT documenta translation e executable-memory mechanics.

## Requisito de equivalência semântica

Interpreter e JIT operam sobre o mesmo ClvmVm state.

O JIT precisa preservar:

- operand-stack semantics;
- call-stack semantics;
- comportamento de VM PC;
- memory checks;
- arithmetic edge cases;
- faults;
- syscall state transitions;
- HALT/YIELD behavior.

Por exemplo, implementações nativas de CALL, CALLI e RET no JIT atualizam os mesmos vm->calls e vm->csp usados pelo interpreter.

Esse shared-state contract permite differential testing entre engines.

## Fronteira de syscalls

CL_OP_SYS transfere de bytecode execution para ClvmSysFn registrado.

No desktop runtime esse callback é clvm_sys_dispatch.

O syscall ID seleciona kernel-side service. Arguments são normalmente retirados da operand stack e results são inseridos quando o serviço possui result.

O bridge atual cobre categorias amplas:

- 2D/3D graphics;
- files/storage;
- input/timing;
- audio;
- memory allocation;
- threads/synchronization;
- networking;
- cryptographic helpers;
- libraries/GC services;
- selected driver/hardware operations.

A numeric syscall ABI pertence ao capítulo dedicado clvm-syscalls.

## Validação de guest pointers em syscalls

Uma syscall não deve tratar integer fornecido pelo guest como kernel pointer já confiável.

Helpers em clvm_sys.c convertem guest offsets apenas depois de checks contra vm->memory e vm->mem_size.

vm_cstr percorre string dentro do guest range e falha se NUL não couber no output capacity e VM bounds.

vm_bytes valida o complete requested buffer length antes de retornar pointer.

Copy helpers validam o range completo antes de transferir bytes.

Assim malformed guest pointers tornam-se syscall failure no bridge normal, em vez de unchecked access.

Toda syscall futura precisa preservar esse invariant.

## Filesystem ownership e limites

A file layer do CLVM registra file objects em bounded global table.

Cada ClvmFile grava owning language slot.

Limites atuais:

    CLVM_FD_MAX       = 32
    CLVM_FD_PER_SLOT  = 8
    CLVM_FD_CAP       = 65536
    máximo de arquivo buffered = 16 MiB

fd_owned verifica se operation usa descriptor pertencente ao caller slot.

Arquivos pequenos podem ser buffered; arquivos maiores podem seguir streaming behavior.

O bridge também rejeita componentes explícitos .. em path_ok e consulta filesystem permissions quando aplicável.

São containment checks úteis, mas não devem ser generalizados como se o parser atual fosse complete capability filesystem ou cobrisse toda possível path-sandbox semantics.

## Driver operations protegidas por capabilities

LangSlot possui capability bits.

Application paths comuns não recebem driver capabilities.

Paths reconhecidos como system drivers recebem CAP_DRIVER, atualmente combinação de PCI, port I/O, MMIO, DMA, IRQ e disk-administration bits.

Hardware-oriented CLVM syscalls chamam drv_cap para verificar required capability antes de executar privileged driver operation.

Isso diferencia claramente ordinary graphics/filesystem calls de driver hardware access.

Capability assignment atual é path-driven, então é project policy mechanism, não cryptographic identity system.

## CLVM threads

O syscall bridge implementa lightweight CLVM thread facility.

Limites atuais:

    CLVM_TH_MAX = 32 globalmente
    CLVM_TH_PER = 8 por slot

Criar child thread aloca e zera outro ClvmVm.

O child compartilha:

- bytecode pointer;
- bytecode size;
- guest memory pointer;
- guest memory size;
- syscall callback/context;
- associated process.

O child possui VM execution state independente, incluindo operand stack, call stack e TLS array.

O initial function PC é fornecido pelo guest e um initial argument é colocado na child operand stack.

## Concorrência com shared memory

Como child VMs compartilham o mesmo guest-memory buffer, ordinary guest memory é shared state entre threads.

Concurrent mutation exige synchronization explícita.

O syscall layer contém mutex/condition support via CLVM synchronization subsystem e pode colocar blocked child VMs em WAITING.

clvm_threads_tick avança runnable child VMs com bounded interpreter slices e acorda parent esperando join quando child termina.

A implementação não equivale a independent-process memory isolation: thread VMs compartilham intencionalmente o guest address space.

## TLS

Cada ClvmVm possui pequeno array tls[16].

Como child thread recebe novo ClvmVm zerado, esse TLS storage é per VM/thread e não parte do shared guest-memory pointer.

Syscalls oferecem bounded indexed access a essas entries.

O array é project runtime facility pequena, não full ELF TLS ABI.

## setjmp e longjmp

CLVM possui guest setjmp/longjmp no VM runtime.

clvm_guest_setjmp grava na guest memory:

- current PC;
- operand stack depth;
- call stack depth;
- active operand-stack values;
- active return PCs.

clvm_guest_longjmp restaura esses valores após validar saved stack depths contra VM limits e coloca longjmp result na stack.

Isso mostra por que operand/call stacks são explicit VM state: nonlocal control transfer pode snapshot e restaurá-las deterministically.

Não há snapshot de todo external kernel resource nem de shared-memory mutations.

## Safepoints e runtime coordination

ChrisC emite SAFEPOINT na entrada de functions, e call operations também marcam safepoint state.

Desktop runtime instala lang_safepoint como VM callback; callback atual executa gc_poll.

Safepoints fornecem lugares em que runtime services podem cooperar com execution sem interromper arbitrariamente toda instruction.

GC/library behavior possui capítulo próprio porque managed object/type metadata e CLS modules excedem o core VM aqui descrito.

## Source maps e debugging

ChrisResult source-map data é escrita junto com CLV output compilado.

No launch, lang_load_map reconstrói mappings de bytecode PCs para source lines e function names.

Debugger state no LangSlot guarda breakpoints, stepping mode, last source line e watch information.

Em debugging, lang_tick consegue executar uma instruction por vez e usar current vm.csp depth com source-line transitions para step behavior.

Fault logging também reporta bytecode PC, mapped line, operand-stack depth, fault code, fault PC e call-stack state.

Assim failures possuem source-oriented diagnostic path em vez de apenas raw VM offsets.

## Teardown e ownership

lang_kill é o authoritative slot teardown path.

Ele:

1. libera JIT executable memory quando presente;
2. libera slot VM RAM conforme ownership model;
3. libera graphics resources;
4. chama clvm_sys_close_slot;
5. libera loaded CLV file buffer;
6. destrói associated process;
7. limpa slot activity, task identity, name e JIT pointers.

clvm_sys_close_slot libera syscall-layer resources owned pelo slot, incluindo shader guest ownership, voxel ownership, input capture, sockets e file descriptors.

Dirty buffered files são flushed pelo file-descriptor teardown path.

Esse cleanup explícito é necessário porque muitos CLVM services alocam kernel-side resources que não desaparecem apenas descartando ClvmVm.

## Hot reload

O language pipeline suporta reload de CLV bytes em named slot existente.

Ele reparsa replacement image, copia para slot-owned storage, reinicializa VM, reanexa memory, restaura selected checkpoint bytes e recarrega source maps.

É uma facilidade de development/runtime, não transparent process migration.

VM execution state é reiniciado e apenas checkpoint state deliberadamente preservado retorna.

Resources fora desse checkpoint seguem seu próprio lifecycle.

## Direção de self-hosting já presente

CLVM também participa do compiler bootstrap path.

lang_disk_cc carrega APPS/CC/CC.CLV, cria process, configura VM region de 16 MiB, inicializa ClvmVm e executa compiler image por clvm_step.

O caller fornece source/destination paths por application argument mechanism.

Depois que guest compiler termina, destination file produzido é carregado e validado novamente por clvm_parse.

Isso é evidência concreta de que CLVM não é apenas demonstration interpreter. Ele participa do caminho do projeto para executar compiler tooling dentro do sistema.

Isso isoladamente não estabelece complete self-hosting de todo ChrisOS.

## Complexidade e limites de armazenamento

Principais bounds e custos atuais:

| Mecanismo | Comportamento atual |
|---|---|
| image parse | O(code size), principalmente checksum |
| interpreter slice | O(instruction budget), excluindo custo específico de syscall |
| operand stack | 256 entries fixas de 64 bits |
| return stack | 64 PCs fixos de 32 bits |
| default guest RAM | 1 MiB |
| maximum CLV code | 16 MiB |
| guest malloc | bump allocation O(1) |
| guest free | sem reclamation |
| guest realloc | O(bytes copiados) |
| thread table | 32 entries globais, scans lineares |
| file table | 32 entries, scans lineares bounded |

Fixed limits tornam operações previsíveis e evitam metadata allocation ilimitada, mas impõem ceilings rígidos.

## Evidência de validação

tools/test_chrisc_c17.c compila e executa subset amplo orientado a C17 através de CLVM.

tools/test_chrisc_fn.c concentra-se em function behavior e VM results.

tools/test_chrisc_doom.c exercita compiler/runtime com programa grande.

tools/test_chrisc_ptr_float.c protege pointer-versus-float argument semantics.

tools/test_fuzz_clvm.c fornece varied input ao parser CLV e valida writer/parser round trips.

tools/test_jit_vm.c e tools/test_jit_native.c exercitam JIT behavior contra VM semantics.

tools/test_editor_vi.c contém regression coverage de call-stack overflow em interpreter/JIT.

O documentation build valida source references e o repository CI executa o project test suite configurado pelo workflow.

Esses testes não significam exhaustive verification de todo CLVM program ou de toda hardware-backed syscall.

## Limitações atuais

Na revisão documentada:

- CLVM possui fixed operand/call stack capacities;
- default guest memory é 1 MiB salvo aumento por runtime policy/image hint;
- guest malloc é bump allocator e free não recupera espaço;
- heap start é heuristic, não formal segmented image layout;
- ordinary ChrisC function storage não é full private per-activation frame model;
- syscall ABI é ampla e aumenta o compatibility surface que interpreter, compiler e kernel precisam preservar;
- capability assignment para driver CLVs é path-based;
- threads compartilham um guest-memory buffer e exigem explicit synchronization;
- runtime usa bounded global thread e file tables;
- JIT compilation pode cair para interpreter durante launch;
- debugging prefere interpreter;
- runtime JIT fault não é automaticamente replayed pelo interpreter;
- CLV checksum detecta corrupção, mas não autentica code;
- CLVM application isolation é runtime/process integration model, não idêntico ao native KCC executable model.

## Fronteira de roadmap

Melhorias futuras podem incluir:

- VM ABI formalmente versionado cobrindo bytecode, calls, syscalls e memory layout;
- per-activation ChrisC frames;
- reclaiming guest allocator;
- capability provenance mais forte que path classification;
- explicit verifier passes antes de execution;
- richer module/link metadata;
- thread/resource tables mais escaláveis;
- structured exception/unwind state;
- code signing ou trust policy mais forte onde necessário;
- differential testing mais amplo interpreter/JIT;
- separação mais clara entre application, driver e managed-library profiles.

São direções futuras até implementation/tests correspondentes existirem.

## Mapa de source e revisão

ChrisC compilation e bytecode lowering ficam em compiler/chrisc/chrisc.c.

CLV image structure e validation são definidos por compiler/clvm/clvm.h e compiler/clvm/clvm_format.c.

VM state machine, stacks, guest allocator e interpreter estão em compiler/clvm/clvm_vm.h e compiler/clvm/clvm_vm.c.

Application lifecycle, VM-memory attachment, interpreter/JIT selection, source maps, scheduling e teardown ficam em compiler/lang_pipeline.c.

Kernel service boundary e slot-owned CLVM resources estão em kernel/lang/clvm_sys.c.

Todas as afirmações de comportamento atual deste capítulo foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
