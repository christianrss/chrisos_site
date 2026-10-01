---
id: clvm-interpreter
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/chrisc/chrisc.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - compiler/jit/jit_compile.c
  - compiler/jit/jit_runtime.c
  - tools/test_editor_vi.c
  - tools/test_jit_vm.c
  - tools/test_chrisc_fn.c
  - tools/test_chrisc_float.c
  - tools/test_store64_copy.c
  - tools/test_doom_jit_diff.c
symbols:
  - clvm_step
  - clvm_vm_init
  - clvm_vm_push64
  - clvm_vm_pop64
  - clvm_vm_wait
  - clvm_vm_wake
  - clvm_fault_text
  - fetch
  - jump_rel16
  - jump_rel32
  - mem_ok
  - fail
  - lang_tick
  - lang_safepoint
  - jit_rt_exec_at_pc
  - jit_rt_run_range
depends_on:
  - clvm-bytecode
  - clvm-memory
  - clvm-syscalls
related:
  - jit
  - jit-memory
  - calling-conventions
  - debugger
  - process-lifecycle
---

# Arquitetura do interpreter CLVM e modelo de execução

## Escopo

O interpreter CLVM é o reference execution engine do bytecode CLV dentro do ChrisOS.

Sua função central é:

    clvm_step(ClvmVm *vm, uint32_t budget)

A função não executa uma aplicação indefinidamente. Ela processa no máximo uma quantidade limitada de bytecode instructions e devolve um scheduling result ao caller.

Isso é importante porque CLVM participa do desktop/application scheduler em vez de controlar a máquina inteira.

O interpreter é simultaneamente:

- bytecode decoder;
- stack machine;
- control-flow engine;
- enforcement point de memory access;
- syscall boundary;
- cooperative execution slice;
- implementação de referência adequada ao debugger;
- baseline semântico usado na comparação com o JIT.

![Loop do interpreter CLVM](../../assets/diagrams/clvm-interpreter-pt-br.svg)

Este capítulo trata execution semantics. O binary CLV format está no capítulo de bytecode, guest RAM no capítulo de memória e service IDs no capítulo de syscalls.

## Estado de execução da VM

ClvmVm contém todo o estado visível ao interpreter de um execution context.

Fields centrais:

| Field | Papel |
|---|---|
| code / code_size | bytecode payload imutável e extensão lógica |
| pc | próximo bytecode address |
| stack[256] / sp | 64-bit operand stack |
| calls[64] / csp | return-PC stack |
| memory / mem_size | guest data memory |
| wake_tick | timer-wait target |
| executed | contador cumulativo de instructions buscadas |
| state | READY, RUNNING, WAITING, HALTED ou FAULTED |
| fault / fault_pc | terminal VM fault record |
| sys / sys_user | host-service callback/context |
| print_ring[8] | valores PRINT recentes para diagnóstico |
| safepoint / on_safepoint | estado/callback de safepoint |
| il_loc[32] | IL-style local slots |
| il_arg[16] | IL-style argument slots |
| tls[16] | pequeno per-VM TLS storage |
| join_wait | estado de thread join |

Operand/call stacks são arrays de capacidade fixa dentro de ClvmVm.

Não são objetos de guest memory.

Essa separação impede ordinary guest STORE de reescrever diretamente stack pointer, call stack ou fault fields do interpreter.

## Inicialização

clvm_vm_init instala a image:

    code      = image->code
    code_size = image->code_size
    pc        = image->entry

Limpa as duas stacks, inicializa um MiB de default guest RAM quando allocation funciona, reseta execution/fault state, instala syscall callback, limpa IL locals/arguments e TLS e escolhe o bump-heap cursor inicial.

O image entry point já foi validado por clvm_parse no load normal de arquivo CLV.

Host tests que montam ClvmImage manualmente precisam fornecer code_size/entry coerentes.

## State machine

Estados públicos:

    READY
      |
      v
    RUNNING
     / |  \
    /  |   \
WAITING HALTED FAULTED
   |
   +---- wake ----> READY

clvm_step trata terminal/waiting states antes de executar.

- WAITING devolve CLVM_STEP_YIELD.
- HALTED devolve CLVM_STEP_HALT.
- FAULTED devolve CLVM_STEP_FAULT.
- READY ou RUNNING entra em RUNNING e começa o loop.

Quando o budget termina normalmente, state volta a READY e o resultado é CLVM_STEP_SLICE.

Logo YIELD não significa necessariamente WAITING. Um yield por process preemption pode ocorrer enquanto state permanece RUNNING.

Caller precisa observar result e state quando essa diferença importa.

## Step results

Resultados para scheduler:

| Result | Significado |
|---|---|
| CLVM_STEP_SLICE | budget esgotado sem halt/fault/wait |
| CLVM_STEP_YIELD | execução deve voltar ao scheduler |
| CLVM_STEP_HALT | HALT atingido ou VM já halted |
| CLVM_STEP_FAULT | terminal VM fault |

São outcomes do execution engine, não source-language return values.

Uma função ChrisC retornar normalmente não gera sozinha CLVM_STEP_HALT; o programa gerado chega posteriormente ao HALT da fronteira principal.

## Decode loop

Para cada unidade de budget, clvm_step:

1. salva pc atual em op_pc;
2. busca um opcode byte;
3. avança pc;
4. incrementa vm->executed;
5. realiza scheduling check em freestanding build;
6. despacha opcode por switch;
7. busca immediate bytes necessários;
8. altera stack, memory, call state ou VM state.

fetch valida:

    pc <= code_size
    requested_count <= code_size - pc

e avança pc depois de aceitar o range.

A forma por subtração evita overflow em pc + count.

## Semântica de budget

Budget é limite de loop iterations, não wall-clock duration.

Um NOP simples e um SYS caro consomem uma unidade cada, embora o host cost seja muito diferente.

Isso mantém VM loop simples, mas faz instruction budget ser apenas aproximação de fairness.

ChrisOS usa em lang_tick:

    LANG_VM_BUDGET_UI   = 4.000.000
    LANG_VM_BUDGET_GAME = 20.000.000

UI programs podem receber até oito slices em um lang_tick pass, sujeito a time/process-slice checks.

Game-sized programs recebem uma slice maior.

Debugger single-step usa budget 1.

## Integração com scheduler

lang_tick percorre até LANG_VM_SLOTS application slots em round-robin.

Em process-backed CLVM, muda para o process address space do slot antes de executar e restaura PROC_KERNEL depois.

Quando JIT está ativo e debugger desligado, lang_tick chama JIT function.

Caso contrário chama clvm_step.

Assim interpreter continua primary debug engine mesmo quando execução normal prefere JIT.

HALT ou FAULT causa teardown do slot.

Faults são logados com pc, source line, sp, fault ID, fault_pc, csp, recent return addresses e top-of-stack.

## Operand stack

Operand stack tem 256 signed 64-bit slots.

clvm_vm_push64 falha quando:

    sp == CLVM_STACK_MAX

clvm_vm_pop64 falha quando:

    sp == 0

Maioria dos opcodes traduz esses helper failures em stack faults explícitos.

Exemplos:

- ADD exige dois valores e empilha um;
- NEG exige um e empilha um;
- LOAD consome address e produz value;
- STORE consome address/value;
- conditional branch consome condition;
- SYS consome service ID após os source-level arguments já terem sido empilhados.

Runtime stack é intencionalmente untyped.

Integers, addresses, float bit patterns e service handles ocupam o mesmo int64_t slot.

O significado de tipo vem do bytecode gerado e da operation consumidora.

## DROP permissivo

CL_OP_DROP difere das demais consuming operations.

Implementação:

    if (sp > 0)
        sp--

DROP com stack vazia é no-op, não CLVM_FAULT_STACK_UNDERFLOW.

Native JIT preserva a mesma policy.

Isso faz parte da current VM semantics e não deve ser alterado apenas em um engine sem decisão de ABI.

## Semântica integer de 64 bits

Arithmetic path principal trabalha com int64_t.

Signed e unsigned division/comparison são famílias separadas.

UDIV, UMOD e unsigned comparisons reinterpretam operands como uint64_t.

Shift count usa:

    count & 63

SHR é logical right shift ao converter left operand para uint64_t.

SAR usa signed right shift.

Division by zero produz CLVM_FAULT_DIV_ZERO.

Signed INT64_MIN / -1 produz CLVM_FAULT_DIV_OVERFLOW.

## Dependência de signed overflow do C

ADD, SUB, MUL, NEG e SHL estão escritos com signed int64_t C expressions.

Exemplos:

    a = a + b
    a = a * b
    -a
    a << (b & 63)

Em ISO C, signed overflow e certos signed left shifts são undefined behavior.

A intenção da VM é efetivamente arithmetic de máquina em two's complement, e x86-64 JIT naturalmente faz wrap em várias dessas operations, mas interpreter source não expressa wrapping explicitamente via uint64_t.

É risco de portabilidade e de interpreter/JIT equivalence.

Implementação mais forte deve definir wrap explicitamente com unsigned arithmetic/conversion ou definir checked overflow como VM fault.

## Floating point

Float opcodes usam 32-bit bit patterns guardados em 64-bit VM slots.

FPUSH coloca 32-bit payload.

FLOAD/FSTORE transferem quatro bytes.

FADD/FSUB/FMUL/FDIV reinterpretam low 32 bits como float, executam native C float operation e empilham resulting bit pattern.

FEQ/FLT/FLE empilham integer booleans.

ITOF converte integer VM value para float.

FTOI converte float para integer.

FDIV faulta explicitamente para divisor float zero.

Interpreter não estabelece VM-specific rounding mode nem NaN canonicalization.

Out-of-range float-to-integer conversion herda comportamento do host C.

Para deterministic cross-architecture execution, edge semantics precisam de especificação mais forte.

## Guest-memory operations

Interpreter aplica bounds em LOAD, STORE, LOAD64, STORE64, LOADB, STOREB, FLOAD, FSTORE e object-field operations.

mem_ok rejeita:

- null backing memory;
- negative guest offsets;
- offsets maiores que mem_size;
- length maior que mem_size - offset.

Memory/ownership completo está no capítulo CLVM memory.

Do ponto de vista do interpreter, invariant principal é:

    ordinary data-memory opcode não calcula
    vm->memory + guest_offset antes de validar todo o range

## Control flow

CLVM suporta:

- 16-bit relative JMP/JZ/JNZ/CALL;
- 32-bit relative JMP32/JZ32/JNZ32/CALL32;
- indirect absolute CALLI;
- absolute-immediate CALLT;
- RET.

Relative displacement é aplicado sobre pc depois do fetch do immediate.

CALL registra esse post-instruction pc como return address antes da transferência.

RET restaura o último return pc.

Call stack suporta 64 return addresses.

Recursion acima disso gera CLVM_FAULT_CALL_OVERFLOW.

RET com csp == 0 gera CLVM_FAULT_CALL_UNDERFLOW.

## Validação de branch targets

jump_rel16/jump_rel32 validam apenas:

    0 <= target < code_size

CALLI usa a mesma regra.

Não verificam se target é início de decoded instruction.

Bytecode manual/corrompido pode saltar para o meio de immediate de PUSH ou outro multi-byte operand e interpretar aquele byte como opcode.

Não existe whole-image control-flow verifier antes da execução.

Isso difere de VMs que validam instruction boundaries e stack effects antecipadamente.

CLV parser valida framing, size, entry e checksum, não o internal control-flow graph.

## Gap de validação em CALLT

CL_OP_CALLT busca absolute target de 32 bits, checa apenas call-stack capacity, registra return pc e faz:

    vm->pc = read_u32(arg)

Não verifica target < code_size.

CALLT fora do range portanto não produz imediatamente CLVM_FAULT_BAD_JUMP.

O próximo opcode fetch falha e normalmente vira CLVM_FAULT_PC.

CALLT in-range mas apontando para mid-instruction também é aceito.

Deve ser alinhado a CALLI/relative calls ou resolvido por verifier.

## Mismatch de diagnóstico em STLOC

LDARG/LDLOC separam immediate availability e slot range.

STLOC combina immediate fetch e stack pop:

    if (!fetch(vm, 1, &arg) || !clvm_vm_pop64(vm, &a))
        return fail(... CLVM_FAULT_TRUNCATED ...)

Se bytecode contém immediate válido de STLOC, mas operand stack está vazia, condição real é stack underflow; interpreter reporta CLVM_FAULT_TRUNCATED.

É bug de diagnostic classification.

Checks precisam ser separados: missing operand bytes -> TRUNCATED; missing stack value -> STACK_UNDERFLOW.

## IL-style locals e arguments

CLVM contém pequena vocabulary adicional para IL-oriented paths.

VM fornece:

    il_arg[16]
    il_loc[32]

LDARG usa one-byte slot 0-15.

LDLOC/STLOC aceitam 0-31.

Arrays ficam dentro de ClvmVm, não em guest memory.

São independentes da operand stack e não são dinamicamente allocated por source-language frame.

É mecanismo leve, não general activation-record system ilimitado.

## Object helper opcodes

NEWOBJ aloca guest memory por clvm_guest_malloc.

Requested size zero vira 16 bytes.

Guest offset resultante é empilhado.

LDFLD/STFLD usam four-byte immediate field offset e acessam oito bytes em:

    object_base + field_offset

CALLT transfere para absolute four-byte target.

LDSTR empilha four-byte immediate como pointer-like guest value; não valida/lê memory nesse momento.

Essas instructions dão suporte a IL/object lowering sem transformar CLVM em fully managed runtime.

## Risco de overflow em field address

LDFLD/STFLD calculam:

    a + (int64_t)off

antes de chamar mem_ok.

Se a estiver próximo de INT64_MAX, signed addition pode overflowar antes do bounds checker.

Compiler-generated guest pointers normais são offsets pequenos, mas adversarial bytecode pode colocar arbitrary int64 values na stack.

É outro ponto em que range arithmetic deveria usar forma unsigned overflow-safe antes de tratar VM como hardened contra malicious bytecode.

## SYS boundary

SYS remove 64-bit value e o trunca para int32_t service ID.

Se callback não existe ou retorna nonzero, VM gera CLVM_FAULT_BAD_SYS em op_pc.

Depois de dispatch bem-sucedido, interpreter define:

    vm->safepoint = 1

e observa state transition feita pelo service:

- WAITING -> CLVM_STEP_YIELD;
- HALTED -> CLVM_STEP_HALT;
- FAULTED -> CLVM_STEP_FAULT.

Argument marshalling e blocking-service issues estão no capítulo de syscalls.

## Safepoints explícitos

CL_OP_SAFEPOINT tem comportamento mais forte que apenas setar safepoint flag.

Interpreter:

1. safepoint = 1;
2. chama on_safepoint se existir;
3. safepoint = 0;
4. em freestanding build verifica process slice.

lang_pipeline instala lang_safepoint, que chama gc_poll.

ChrisC emite SAFEPOINT na entrada de cada função.

Assim generated function calls comuns chegam rapidamente a explicit GC polling point.

x86-64 JIT também emite native safepoint callback sequence para CL_OP_SAFEPOINT.

## Safepoint flag em calls

CALL, CALL32, CALLI, NEWOBJ e SYS bem-sucedido definem safepoint = 1 no interpreter, mas não chamam on_safepoint diretamente nem limpam o flag nesses casos.

Generated ChrisC functions iniciam com explicit SAFEPOINT, que executa callback e limpa o flag.

Em manually assembled flow que não chega a SAFEPOINT, flag pode permanecer setado por mais tempo.

Portanto o field não significa sozinho que callback acabou de executar.

## Instruction counter

vm->executed incrementa depois do fetch do opcode byte e antes da execução semântica.

É cumulativo entre slices.

Em freestanding build, a cada 8192 fetched instructions interpreter consulta proc_slice_due.

A posição atual desse check cria issue importante.

## Bug de preemption antes da execução

A sequência atual é:

    fetch opcode -> pc avança
    executed++
    if ((executed & 8191) == 0 && proc_slice_due())
        return YIELD
    executar opcode

Se proc_slice_due estiver true nesse checkpoint, clvm_step retorna antes de executar opcode já fetched.

Como pc já avançou, próxima chamada começa na instruction seguinte.

A instruction fetched é perdida.

É concrete interpreter correctness bug sob process preemption.

Scheduling check precisa ocorrer antes de consumir opcode, depois de executá-lo, ou restaurar pc = op_pc antes do return.

Regression test deve forçar proc_slice_due exatamente no boundary de 8192 instructions e provar que nenhuma instruction é omitida.

## READY versus RUNNING na preemption

Early preemption return também pula:

    vm->state = CLVM_READY

do fim normal do budget.

Assim VM pode devolver CLVM_STEP_YIELD com state ainda CLVM_RUNNING.

lang_tick consegue chamar clvm_step novamente porque RUNNING é aceito como executable state, então não é imediatamente fatal.

Porém result/state invariants ficam menos limpos.

Scheduler contract deveria definir explicitamente se preemption YIELD deixa RUNNING ou volta a READY.

## Wait e wake

clvm_vm_wait grava wake tick e define WAITING.

clvm_vm_wake faz wrap-safe signed-difference test de 32 bits:

    (int32_t)(now - wake_tick) >= 0

e restaura READY ao chegar no target.

Timer wait portanto não busy-loopa dentro de clvm_step.

lang_tick chama clvm_vm_wake antes de executar cada slot.

Outras blocking syscall families usam runtime/process state adicional e são tratadas no capítulo de syscalls.

## HALT

HALT é terminal para a VM instance.

Interpreter define:

    state = CLVM_HALTED

e retorna CLVM_STEP_HALT imediatamente.

Nova chamada a clvm_step devolve HALT sem buscar bytecode.

lang_tick trata HALT como application termination e faz teardown do slot.

Não existe source-level process exit code separado guardado pelo interpreter.

## Fault model

fail grava:

    vm->fault
    vm->fault_pc
    vm->state = CLVM_FAULTED

e retorna CLVM_STEP_FAULT.

Classes:

| Fault | Trigger |
|---|---|
| PC | falha ao buscar próximo opcode / execution pc inválido |
| OPCODE | unknown opcode ou invalid IL slot |
| TRUNCATED | missing immediate bytes |
| STACK_UNDERFLOW | required operand ausente |
| STACK_OVERFLOW | operand stack cheia |
| CALL_UNDERFLOW | RET sem caller |
| CALL_OVERFLOW | call stack cheia |
| DIV_ZERO | integer/float divide-by-zero path |
| DIV_OVERFLOW | signed INT64_MIN / -1 |
| BAD_ADDRESS | guest memory access rejeitado |
| BAD_JUMP | checked branch/call fora do code |
| BAD_SYS | syscall callback ausente/rejeitado |

Fault state é sticky: chamadas posteriores devolvem CLVM_STEP_FAULT sem executar.

## Bug no failure path com VM nula

clvm_step inicia com:

    if (vm == NULL || vm->code == NULL)
        return fail(vm, CLVM_FAULT_PC, 0)

Mas fail escreve imediatamente através de vm.

Logo branch vm == NULL não devolve VM fault de forma segura; dereference null pointer.

Caso code == NULL funciona porque vm existe.

É bug de host-side API e deve retornar CLVM_STEP_FAULT sem dereference ou rejeitar null antes de fail.

Execução normal do ChrisOS passa ClvmVm real, mas public C API deve manter null behavior coerente.

## PRINT e diagnóstico

PRINT retira um VM value e o registra em rolling ring de oito entries.

Depois de cheio, entries antigas deslocam para esquerda e newest ocupa índice 7.

É diagnostic state, não console I/O para usuário.

Text output normal passa por services como fwrite.

O JIT helper path para PRINT não mantém claramente o mesmo print ring em jit_runtime.c, então PRINT diagnostics não devem ser assumidos idênticos entre todos os execution modes.

## Integração com debugger

Debug mode usa intencionalmente o interpreter.

Single instruction:

    clvm_step(vm, 1)

Line stepping executa repetidamente budget-1 até source-line/depth criteria ou HALT/FAULT.

Source map em lang_pipeline traduz bytecode PCs para source file/line.

Debugger consegue inspecionar:

- pc;
- stack values;
- call depth/return PCs;
- guest memory;
- fault state;
- recent syscall trace.

Isso torna precise fault_pc semantics importante.

## Contract interpreter/JIT

Interpreter não é apenas fallback de performance.

É semantic reference usada em differential/focused tests.

JIT emite native x86-64 para muitos opcodes e usa runtime helpers para outros.

Ambos compartilham layout de ClvmVm e devem concordar em:

- stack effects;
- branch/call targets;
- memory width/bounds;
- state transitions;
- fault categories;
- syscall behavior;
- safepoint callbacks;
- HALT/YIELD outcomes.

O capítulo seguinte de JIT documenta lowering nativo.

Para interpreter, a regra importante é: comportamento usado por compiler-generated CLV precisa de equivalente no JIT ou boundary de suporte explícita.

## Performance

Switch interpreter possui O(1) dispatch por opcode simples.

Memory operations são O(1) para widths fixos 1/4/8 bytes.

CALL/RET O(1).

Relative branch validation O(1).

PRINT O(1) com tiny fixed ring shift.

SYS é dominado pelo subsystem.

Interpreter não usa decode cache/predecoded instruction table; immediates são decodificados do bytecode em toda execução.

Isso simplifica observabilidade, mas é mais lento que JIT em hot loops.

## Cache e locality

Hot set principal:

- sequential code bytes;
- ClvmVm stack/call arrays;
- poucos scalar VM fields.

Straight-line bytecode tem boa code-data locality.

Guest LOAD/STORE locality depende da aplicação.

Operand/call stack fixas dentro de ClvmVm mantêm endereços estáveis e compactos.

Switch dispatcher pode ter branch-prediction cost em streams de opcodes mistos.

## Concurrency e reentrancy

clvm_step opera sobre um ClvmVm e não usa process-global decode state.

VMs distintas têm stacks/calls/PCs separados.

Porém callbacks via SYS/on_safepoint podem acessar global kernel state.

Process-backed vm->memory só é válido no intended address-space context, então lang_tick muda para process antes da execução.

Interpreter não é independente de scheduler/address-space discipline apenas porque decode loop é per-VM.

## Security boundary

Interpreter oferece containment útil:

- code reads bounded por code_size;
- data-memory operations bounded por mem_size;
- operand/call stacks com limites fixos;
- syscall entry explícita;
- faults terminam execução da VM.

Ainda não é hardened bytecode sandbox.

Gaps atuais incluem:

- ausência de instruction-boundary verifier;
- ausência de pre-execution stack-effect verification;
- unchecked CALLT target;
- signed-overflow-sensitive arithmetic;
- overflow-sensitive field-address addition;
- null-VM host API bug;
- preemption capaz de pular instruction fetched;
- service-level issues documentados nos capítulos de syscall/memory.

Claims de segurança devem ficar limitadas aos checks existentes.

## Evidência de validação

tools/test_editor_vi.c exercita interpreter fallthrough e verifica recursion overflow produzindo CLVM_FAULT_CALL_OVERFLOW; também compara o mesmo overflow com JIT.

tools/test_jit_vm.c compila loop com wait, executa interpreter/JIT, acorda VMs em YIELD e compara resulting VM state.

tools/test_chrisc_fn.c exercita generated function calls, integer results e float arguments/results.

tools/test_chrisc_float.c valida float multiplication e guest-memory result bits.

tools/test_store64_copy.c executa sequência explícita LOAD64/STORE64 em interpreter e JIT com backing de 32 MiB.

tools/test_doom_jit_diff.c faz step-oriented interpreter/JIT comparison em Doom-related bytecode paths.

O corpus ChrisC mais amplo exercita arrays, structures, pointer widths, calls, branches e generated code.

Ainda faltam adversarial focused tests para os gaps identificados.

## Focused tests ausentes

Devem ser adicionados testes para:

- clvm_step(NULL, budget);
- truncated immediate versus stack-underflow em STLOC;
- CALLT fora de code_size;
- jumps para immediate bytes;
- exact 8192-boundary preemption com proc_slice_due asserted;
- signed 64-bit wrap semantics;
- field-address addition perto de INT64_MAX;
- explicit SAFEPOINT callback count;
- DROP em empty stack como compatibility rule;
- PRINT-ring parity entre interpreter/JIT caso esse diagnostic seja comum aos dois.

## Limitações atuais

Na revisão documentada:

- interpreter decodifica bytecode a cada execução em vez de verified predecode;
- branch targets são range-checked, não instruction-boundary checked;
- CALLT não faz range check do absolute target;
- STLOC pode reportar TRUNCATED em operand-stack underflow;
- clvm_step(NULL, ...) segue null-dereferencing failure path;
- freestanding 8192-instruction preemption check pode pular opcode já fetched;
- preemption YIELD pode deixar state RUNNING;
- signed arithmetic/left-shift depende de host C em overflow cases;
- object field-address addition pode overflowar antes de mem_ok;
- float edge semantics não são totalmente normalizadas entre architectures;
- CALL/NEWOBJ/SYS safepoint flag behavior não equivale à execução de CL_OP_SAFEPOINT;
- PRINT diagnostic behavior não está claramente equivalente no JIT helper;
- não existe whole-program verifier para stack depth, types ou control-flow targets.

## Fronteira de roadmap

Interpreter mais forte pode adicionar:

- verifier que decodifica cada instruction uma vez e cria instruction-start bitmap;
- verified control-flow targets e stack effects;
- explicit wraparound integer helpers;
- overflow-safe address arithmetic;
- preemption point corrigido após instruction;
- pending-syscall continuations precisas;
- unified safepoint semantics;
- generated opcode metadata compartilhada por assembler/interpreter/JIT/docs;
- exhaustive interpreter/JIT differential tests para todos opcodes/faults;
- optional decode cache ou direct-threaded dispatch em builds sem JIT.

São mudanças futuras até implementação/testes correspondentes existirem.

## Mapa de source e revisão

compiler/clvm/clvm_vm.h define ClvmVm, state/fault/result enums e stack capacities.

compiler/clvm/clvm_vm.c implementa initialization, stack helpers, state transitions, bounds checks e clvm_step.

compiler/clvm/clvm.h define opcode numbers e CLV image metadata.

compiler/chrisc/chrisc.c emite CLVM instructions e insere SAFEPOINT em function entry.

compiler/lang_pipeline.c integra interpreter com process switching, debugging, budgets, safepoints e slot teardown.

compiler/jit/jit_compile.c e compiler/jit/jit_runtime.c fornecem alternate JIT execution engine usado para comparison.

Todas as afirmações de comportamento atual deste capítulo foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
