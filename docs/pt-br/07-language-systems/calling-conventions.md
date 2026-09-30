---
id: calling-conventions
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.c
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/il/il.h
  - compiler/il/il.c
  - compiler/jit/jit_compile.c
  - compiler/jit/jit_runtime.c
  - tools/test_kcc.c
  - tools/test_chrisc_c17.c
  - tools/test_chrisc_ptr_float.c
  - tools/test_editor_vi.c
symbols:
  - parse_args
  - arg_reg
  - parse_params
  - alloc_slot
  - temp_slot
  - epilogue
  - emit_return_address
  - FuncDef
  - gen_call
  - emit_call
  - chrisc_emit
  - ClvmVm
  - CLVM_STACK_MAX
  - CLVM_CALL_MAX
  - CL_OP_CALL
  - CL_OP_CALL32
  - CL_OP_CALLI
  - CL_OP_CALLT
  - CL_OP_RET
depends_on:
  - intermediate-representation
  - native-codegen
related:
  - chrisc-clvm
  - clvm-bytecode
  - kcc
  - jit
---

# Convenções de chamada e stack frames

## Escopo

Uma calling convention define o contrato entre caller e callee: onde arguments são colocados, onde results retornam, como return address é preservado, quais machine ou virtual registers pertencem a cada lado, como stack alignment é mantido e o que constitui uma function activation.

ChrisOS possui atualmente dois modelos de chamada materialmente diferentes.

O caminho nativo do KCC usa uma convenção x86-64 baseada em registers e stack cuja ordem de arguments inteiros e pointers segue a conhecida sequência System V AMD64.

O caminho ChrisC/CLVM não é um hardware ABI. Ele usa VM operand stack, return-address stack separada e guest-memory scratch areas gerenciadas pelo compiler para arguments comuns de ChrisC.

Esses contratos não devem ser descritos como intercambiáveis.

![Convenções de chamada no ChrisOS](../../assets/diagrams/calling-conventions-pt-br.svg)

## Modelo de chamadas nativo do KCC

O caller do KCC avalia cada argument expression e armazena o value resultante em temporary frame slot. Depois que todos os arguments foram avaliados, ele recarrega os values para suas posições de chamada.

As seis primeiras posições usam:

| Posição | Register |
|---:|---|
| 0 | RDI |
| 1 | RSI |
| 2 | RDX |
| 3 | RCX |
| 4 | R8 |
| 5 | R9 |

Essa ordem coincide com a ordem de integer/pointer arguments do System V AMD64 ABI.

A semelhança não torna a implementação atual do KCC uma implementação completa do System V C ABI. KCC suporta um C profile restrito, não implementa as regras completas de floating-point argument classification, não implementa aggregate classification equivalente à de um production ABI e usa backend simples de fixed frame.

A descrição correta é, portanto: **calling convention SysV-like para integer/pointer dentro do subset suportado pelo KCC**.

## Ordem de avaliação dos arguments

parse_args processa source arguments da esquerda para a direita.

Para cada argument ele:

1. faz parse da expression;
2. materializa o value;
3. armazena RAX em temporary slot;
4. segue para o próximo argument.

Somente depois da lista completa os values salvos são movidos para argument registers ou stack slots.

Isso dá ao KCC comportamento concreto left-to-right na revisão atual.

É um fato de implementation, não uma garantia portável da linguagem C que source deva assumir entre compiladores diferentes.

O staging temporário também impede que a avaliação de expressions posteriores destrua values já computados em RAX.

## Arguments na stack

Arguments depois dos seis primeiros são gravados pelo caller numa outgoing stack area temporária.

Se existem n arguments extras:

    extra = n - 6
    slots = extra arredondado para quantidade par
    bytes = slots * 8

KCC subtrai esse total de RSP, grava argument 6 em [rsp], argument 7 em [rsp+8] e assim por diante, executa a chamada e depois adiciona o mesmo total de volta a RSP.

Arredondar a área para número par de slots de oito bytes preserva 16-byte stack alignment quando o frame gerado ao redor já está alinhado.

O slot adicional, quando existe, é padding de alinhamento, não argument.

## Stack alignment

Uma function gerada usa:

    push rbp
    mov rbp, rsp
    sub rsp, 2048

Em chamada recebida com o alignment esperado, CALL já colocou return address de oito bytes. push rbp consome mais oito, retornando RSP para boundary de 16 bytes. A subtração de 2048 preserva alignment porque 2048 é divisível por 16.

A outgoing stack area para arguments também é múltipla de 16.

Assim o call path gerado pelo KCC mantém um alignment invariant consistente para chamadas produzidas pelo próprio compiler.

Ainda não é correto inferir complete external ABI compatibility apenas dessa propriedade; alignment é somente uma parte do ABI.

## Layout do frame nativo

O stack frame atual é propositalmente simples.

Conceitualmente:

    endereços maiores

    [rbp + 24]   stack argument 7
    [rbp + 16]   stack argument 6
    [rbp +  8]   return address
    [rbp +  0]   RBP anterior
    [rbp -  8]   local / register argument salvo
    [rbp - 16]   local
       ...
    região de temporary spills
       ...
    RSP atual após reserva fixa

    endereços menores

alloc_slot atribui ordinary local slots em offsets negativos. Cada slot ocupa no mínimo oito bytes e é arredondado para alignment de oito.

O ordinary local allocator é limitado a 1536 bytes.

Expression temporary slots usam região separada de offsets negativos começando aproximadamente em -1600 e são reiniciados entre statements através de g_ntemp.

A function reserva 2048 bytes, então as duas regiões cabem no frame model atual.

## Incoming register parameters

parse_params atribui aos seis primeiros formal parameters ordinary local frame slots.

Na function entry, KCC move o incoming argument register para RAX e grava RAX no frame slot do parameter.

Assim referências posteriores normalmente não continuam lendo RDI, RSI ou outros incoming registers. Elas acessam ordinary local memory.

É uma simplificação deliberada.

Ela evita manter formal parameters vivos em registers específicos ao longo da function, ao custo de stores na entrada e reloads posteriores.

## Incoming stack parameters

Formal parameters depois do sexto não são copiados para negative local slots.

O valor Sym.frame é:

    16 + (index - 6) * 8

logo parameter 6 resolve em [rbp+16].

O layout deriva diretamente de:

- saved RBP em [rbp];
- hardware return address em [rbp+8];
- primeiro caller stack argument em [rbp+16].

O callee não remove esses arguments. O caller é owner da outgoing area e restaura RSP depois da call.

## Return address

No caminho nativo x86-64, a instruction CALL coloca o return instruction pointer na stack.

KCC preserva esse address mantendo o frame convencional.

O builtin suportado que expõe o return address da function atual carrega:

    [rbp + 8]

confirmando o frame model gerado.

RET consome esse hardware return address depois que o epilogue restaura RSP e RBP.

## Return values

Returns com expression deixam o value computado em RAX.

O return statement então emite:

    mov rsp, rbp
    pop rbp
    ret

Consequentemente, o caller recebe scalar/pointer results suportados em RAX.

Um void return emite o epilogue sem definir language-level result.

Native floating-point return convention não é contrato geral suportado na revisão documentada, pois floating-point native value operations continuam fora do subset do KCC.

## Direct e indirect native calls

Uma direct call emite:

    call symbol

Function-pointer call avalia o target, salva, recarrega em RAX depois de preparar arguments e emite:

    call rax

Argument locations são as mesmas nos dois casos.

A diferença está apenas na origem do control-transfer target.

Isso também importa para ChrisAsm/ChrisLd: symbolic direct calls podem criar object relocations, enquanto register-indirect calls não possuem call-target relocation em link time.

## Ownership de registers

O código atual gerado pelo KCC usa principalmente volatile/caller-scratch registers como RAX, RCX e RDX, além dos argument registers.

RBP é explicitamente preservado como frame pointer.

O generator não possui general register allocator que coloque long-lived values em RBX ou R12-R15 e depois produza um conjunto sistemático de callee saves.

Assim, o compiler evita parte da complexidade de callee-saved register management simplesmente por não explorar agressivamente o conjunto maior de registers.

Inline assembly exige cuidado porque pode escapar às premissas feitas pelo syntax-directed generator.

## Limites de parameters e arguments do KCC

KCC define KCC_PARAM_MAX como 16.

parse_args e parse_params aplicam esse modelo finito.

Isso limita arrays temporários e simplifica o compiler, mas é implementation limit e não limite arquitetural do x86-64.

A calling convention suportada deve ser entendida junto com o language subset suportado.

## CLVM possui duas stacks

ClvmVm contém:

    int64_t stack[CLVM_STACK_MAX]
    uint16_t sp

para operand values e:

    uint32_t calls[CLVM_CALL_MAX]
    uint16_t csp

para return addresses.

Na revisão atual:

    CLVM_STACK_MAX = 256
    CLVM_CALL_MAX  = 64

A return stack é separada da operand stack.

Uma function call não cria hardware-style frame com saved base pointer, locals e arguments.

CALL, CALL32 e CALLI manipulam apenas control-flow return state. Arguments e local storage usam mecanismos distintos.

## CLVM direct calls

Para CL_OP_CALL e CL_OP_CALL32, o interpreter:

1. decodifica relative target;
2. verifica capacidade da call stack;
3. grava current post-instruction PC em calls[csp];
4. incrementa csp;
5. marca safepoint;
6. salta ao target.

O único estado salvo é return PC.

Não há snapshot de operand-stack pointer nem local-variable frame record.

RET verifica underflow, decrementa csp e restaura PC de calls[].

Call depth acima de 64 gera CLVM_FAULT_CALL_OVERFLOW.

RET com call stack vazia gera CLVM_FAULT_CALL_UNDERFLOW.

## CLVM indirect calls

CL_OP_CALLI recebe target da operand stack.

O interpreter retira um 64-bit value, verifica que target está dentro do bytecode image, salva return PC em calls[] e atribui o target a vm->pc.

Isso oferece function-pointer-style control transfer para código gerado por ChrisC.

O target é absolute bytecode offset, não host native address.

A range check é importante integrity boundary da VM.

## Transporte de arguments no ChrisC

Ordinary ChrisC function arguments não usam atualmente CL_OP_LDARG.

O compiler reserva uma guest-memory scratch area.

Durante chrisc_emit:

    icall_base = align8(mem_next)
    size       = FUNC_ARG_MAX * 8

FUNC_ARG_MAX vale 16, logo a ordinary call scratch area contém dezesseis slots de oito bytes.

Uma varargs region separada reserva mais 32 entries de oito bytes.

Em direct call site, ChrisC avalia cada argument e o grava em:

    icall_base + index * 8

usando store path apropriado.

Para ordinary integers e pointers o slot é de 64 bits.

By-value float scalars usam float store path.

Pointer values sempre continuam pointer-width, mesmo quando apontam para float; essa distinção é protegida por pointer/float regression tests.

## Entrada do callee ChrisC

Cada FuncDef registra o guest-memory address atribuído a cada formal parameter.

Quando o compiler emite o início de uma function, primeiro emite SAFEPOINT e depois copia cada incoming value do shared icall scratch para o fixed guest-memory address do formal parameter.

Conceitualmente:

    scratch arg 0 -> storage do parameter 0
    scratch arg 1 -> storage do parameter 1
    ...

O copy width depende de parameter width e float classification registrados.

Depois dessas cópias, o function body lê parameter symbols como outras guest-memory variables.

Não existe etapa de alocação de CLVM activation record equivalente a native stack frame.

## Return-value convention do ChrisC

ChrisC retorna values pela VM operand stack.

Um non-main return com expression deixa um value na stack e emite RET.

Void return ainda faz push de zero antes de RET.

O compiler preserva deliberadamente o invariant de que uma normal function call deixa exatamente um operand-stack value, inclusive para void callees.

Callers que usam void function como statement podem então executar DROP desse placeholder dentro da regra normal de expression statement.

main é especial: sua return expression é removida e execução termina com HALT em vez de RET.

## Shared scratch e semântica de activation

A convention atual do ChrisC não cria private argument area para cada activation.

icall_base é uma única scratch region reservada pelo compiler e compartilhada pelas calls geradas na VM image.

Formal parameter storage associada a cada function também é alocada em guest memory durante compilation, não dinamicamente por invocation.

A CLVM return stack fornece nested **control-flow** activations, mas não fornece automaticamente independent argument/local storage por call.

Essa distinção é crítica.

Recursive ou re-entrant execution geral exige per-activation storage para values que precisam sobreviver a nested invocation. O design atual com fixed storage não deve ser descrito como conventional recursive stack-frame model.

Da mesma forma, nested calls durante a construção de argument posterior reutilizam a mesma incoming scratch area. O compiler possui proteção para seu AST argument-index bookkeeping, mas o runtime call scratch continua sendo memória compartilhada.

Código que depende de arbitrary re-entrant C activation semantics não deve ser assumido correto sem regression test específico do caso exigido.

## Varargs no ChrisC

ChrisC reserva va_base imediatamente depois da ordinary call scratch area.

Extra arguments de variadic function são armazenados ali em eight-byte slots.

va_start inicializa uma variável semelhante a va_list para essa base.

va_arg avança nessa memory de acordo com a representation suportada pelo compiler.

É VM calling mechanism específico do projeto.

Não é a System V AMD64 varargs register-save-area ABI.

## CLVM IL argument/local opcodes

O CLVM instruction set também possui:

    LDARG
    LDLOC
    STLOC
    CALLT

ClvmVm contém arrays fixos:

    il_arg[16]
    il_loc[32]

Eles pertencem às facilidades pequenas de IL/CLA documentadas com compiler/il.

Não são o transporte utilizado pelas ordinary ChrisC calls acima.

Também não são empilhados e restaurados como arrays independentes em cada CALLT na estrutura atual do VM state.

A documentação não deve apresentar LDARG/LDLOC como se ChrisC utilizasse managed per-method frame convencional.

## Equivalência interpreter/JIT

O CLVM JIT implementa o mesmo call-stack state do interpreter.

Para CALL/CALL32, verifica csp, grava next bytecode PC no array calls e despacha para target.

CALLI retira bytecode target, valida o range, salva return address e despacha.

RET decrementa csp e recarrega vm->pc de calls[].

O host machine code gerado é aceleração da VM calling semantics. Ele não substitui essa semântica pelo native KCC ABI.

Essa distinção é necessária para interpreter/JIT equivalence.

## Safepoints

CLVM call instructions marcam safepoint state.

Isso permite que runtime services como GC ou scheduler-related work observem execution boundaries bem definidos.

SAFEPOINT opcodes também podem aparecer explicitamente nas function entries geradas pelo ChrisC.

Uma VM call participa de runtime coordination que uma native CALL simples não oferece automaticamente.

## Fault containment

Calling-convention failures são tratados de forma diferente nos dois execution paths.

Native KCC code depende da call/return mechanics do x86-64 e de generated stack discipline correta. Native stack malformada pode corromper control flow diretamente.

CLVM valida call-stack overflow, call-stack underflow e indirect call target range e converte falhas em ClvmFault.

A VM value stack detecta independentemente operand underflow e overflow.

A diferença reflete o protection model distinto entre native execution e managed VM execution.

## Performance e trade-offs

A convention do KCC é barata na call boundary: os seis primeiros supported arguments usam registers e RET usa hardware state.

O backend simples, porém, faz muitos spills e copia incoming register parameters imediatamente para memory.

ChrisC/CLVM evita host ABI dependency e mantém virtual ISA pequena, mas argument passing via guest-memory scratch adiciona VM loads/stores.

A CLVM return-address stack é compacta e bounded, mas sua capacidade fixa limita nested call depth.

Um futuro per-activation CLVM frame melhoraria re-entrancy ao custo de runtime state e frame management adicionais.

## Evidência de validação

tools/test_kcc.c exercita function definitions, direct calls, pointer behavior e generated native assembly.

tools/test_chrisc_c17.c exercita ordinary ChrisC functions e construções de linguagem.

tools/test_chrisc_ptr_float.c protege especificamente a regra de que float pointer continua pointer de 64 bits quando passado como argument, sem truncamento pelo scalar-float path.

tools/test_editor_vi.c contém regression coverage interpreter/JIT para CLVM call-stack overflow, validando que ambos os engines faultam de forma consistente no call-depth bound.

Esses testes sustentam os contracts descritos aqui, mas não provam complete System V ABI compatibility nem unrestricted recursive ChrisC semantics.

## Limitações atuais

Na revisão documentada:

- KCC implementa convention SysV-like focada em integer/pointer, não AMD64 ABI completo;
- KCC suporta no máximo 16 source-level parameters/arguments nos arrays atuais;
- native floating-point calling rules não formam contrato geral suportado;
- KCC reserva fixed 2048-byte frame em vez de calcular exact frame size;
- KCC não possui general register allocation nem uso sistemático de todos callee-saved registers;
- ChrisC passa ordinary arguments por shared guest-memory call scratch region;
- formal/local storage do ChrisC não é private runtime frame por invocation;
- CLVM calls preservam return PCs, não complete activation records;
- CLVM return depth é limitado a 64;
- CLVM operand stack é limitada a 256 values;
- IL argument/local arrays são fixed VM state, não full per-call managed frame stack;
- native e CLVM calling conventions são contratos separados.

## Fronteira de roadmap

Um future native backend poderia evoluir da convention atual para ABI profile formalmente especificado com complete aggregate, floating-point, variadic e callee-save behavior.

Um future CLVM calling model poderia introduzir activation records explícitos contendo:

- return PC;
- operand-stack base;
- argument area;
- local area;
- varargs metadata;
- debug/source frame identity;
- GC roots;
- exception/unwind state.

Isso tornaria recursion e re-entrancy explícitas em vez de depender de fixed guest-memory locations.

Essas mudanças afetariam bytecode compatibility e interpreter/JIT behavior e exigiriam versioned specification e differential tests.

São arquitetura futura até implementação correspondente existir.

## Mapa de source e revisão

O native calling path está em compiler/kcc/kcc.c, principalmente parse_args, arg_reg, parse_params, alloc_slot, temp_slot, function prologue emission, epilogue e return handling.

O contract de arguments/results do ChrisC está em compiler/chrisc/chrisc.c por meio de FuncDef, gen_call, emit_call, chrisc_emit e return generation.

As VM return-address e operand stacks são definidas em compiler/clvm/clvm_vm.h e executadas em compiler/clvm/clvm_vm.c.

As transições equivalentes de CALL/CALLI/RET no JIT ficam em compiler/jit/jit_compile.c.

Todas as afirmações de comportamento atual deste capítulo foram reconciliadas com a revisão ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56.
