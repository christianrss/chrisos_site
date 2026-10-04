---
id: clvm-spec
lang: pt-br
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_format.c
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/clvm/clasm.h
  - compiler/clvm/clasm.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.h
  - kernel/lang/clvm_sys.c
  - kernel/lang/clvm_sync.h
  - compiler/jit/jit.c
  - tools/test_clasm.c
  - tools/test_clasm_games.c
  - tools/test_clvm_sync.c
  - tools/test_fuzz_clvm.c
symbols:
  - clvm_parse
  - clvm_write_image
  - clvm_write_image_v2
  - clvm_vm_init
  - clvm_vm_set_memory
  - clvm_step
  - clvm_sys_dispatch
  - clvm_guest_malloc
  - clvm_guest_realloc
  - clvm_guest_setjmp
  - clvm_guest_longjmp
depends_on:
  - specifications-policy
  - clvm-bytecode
  - clvm-memory
  - clvm-syscalls
  - clvm-interpreter
related:
  - chrisc-clvm
  - jit
  - debugger
  - gc-libraries
---

# Especificação do executável e da máquina virtual CLVM

## Status

CLVM é a máquina virtual de stack usada pelo pipeline de execução do ChrisC.

Esta especificação descreve o container executável, o estado do interpreter, o encoding do bytecode, o modelo de memória, regras de control flow, faults e a fronteira de syscalls implementados na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` do ChrisOS.

O formato atual do container é **versão 2**. O loader também aceita versão 1.

## Separação arquitetural

CLVM possui três contratos distintos:

1. o container executável serializado `.CLV`;
2. o instruction set de bytecode;
3. o estado runtime da VM e o ABI de syscalls do host.

O container define onde o código começa, qual é o entry point e quanta guest memory é solicitada.

O bytecode define operações determinísticas da stack machine.

O host fornece scheduling, system services, graphics, files, networking, threads e outros serviços por meio de `SYS`.

## Magic do arquivo

Toda CLVM image começa com:

    43 4c 56 4d

ou ASCII:

    C L V M

Qualquer outro magic é rejeitado.

## Versões

Constantes:

    CLVM_VERSION    = 2
    CLVM_VERSION_V1 = 1

O header v1 possui 16 bytes.

O header v2 possui 24 bytes.

## Byte order

Todos os fields multibyte no container usam encoding little-endian explícito.

Instruction immediates e integer load/store na guest memory também são little-endian.

Isso faz parte do binary contract da CLVM.

## Header versão 1

Layout v1:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | magic "CLVM" |
| 4 | 1 | version = 1 |
| 5 | 1 | flags |
| 6 | 2 | entry |
| 8 | 4 | code size |
| 12 | 4 | code checksum |

O code começa no offset 16.

O entry point v1 fica limitado a 16 bits.

O writer legado também limita code size a 65535 bytes.

## Header versão 2

Layout v2:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | magic "CLVM" |
| 4 | 1 | version = 2 |
| 5 | 1 | flags |
| 6 | 2 | reserved, atualmente zero |
| 8 | 4 | code size |
| 12 | 4 | code checksum |
| 16 | 4 | entry |
| 20 | 4 | memory hint |

O code começa no offset 24.

A v2 amplia o range do executável e do entry point e acrescenta o memory-size hint.

## Limite de code size

O parser aceita no máximo:

    CLVM_MAX_CODE = 16 MiB

Também exige:

    code_size == file_size - header_size

Portanto o arquivo possui exatamente um bytecode body depois do header.

Trailing payload não faz parte do formato atual.

## Entry point

O entry é um byte offset dentro do code array.

O loader exige:

    entry < code_size

O interpreter inicia:

    pc = image.entry

Não existe symbol table ou resolução de nome de entry dentro do container CLVM.

## Flags

O único flag atualmente reconhecido é:

    CLVM_FLAG_GAME = 0x01

Bits desconhecidos causam rejeição.

O flag é metadata para o host; isoladamente não muda o decoding de instructions.

## Memory hint

A versão 2 acrescenta:

    mem_hint

Esse field solicita uma guest-memory capacity ao host.

Zero significa "usar o default do host".

O initializer standalone da VM aloca:

    CLVM_MEMORY_SIZE = 1 MiB

O language pipeline do ChrisOS pode anexar memória maior. Programas grandes podem solicitar dezenas de MiB; o pipeline atual usa hint de 32 MiB para games suficientemente grandes.

O memory hint é uma solicitação de capacidade, não um memory-map description.

## Checksum do bytecode

O container armazena FNV-1a de 32 bits sobre os bytes de code.

Algoritmo:

    hash = 2166136261
    para cada byte:
        hash ^= byte
        hash *= 16777619

Mismatch é rejeitado.

O header não participa desse checksum.

## Classes de erro do loader

O parser classifica:

- null argument;
- arquivo menor que o header;
- magic inválido;
- version não suportada;
- flags não suportados;
- code size inválido;
- entry fora do bytecode;
- checksum mismatch;
- output-capacity failure nos writers.

Uma image válida é size-checked antes de executar.

## Estado central da VM

O runtime mantém:

- code pointer e code size;
- program counter;
- operand stack;
- call stack;
- linear guest memory;
- wake tick;
- executed-instruction counter;
- state/fault;
- syscall callback e host context;
- print history;
- safepoint state;
- guest heap cursor;
- IL locals e arguments;
- TLS slots;
- thread-join state.

Nada disso, além do que está no header, é mutable runtime state serializado no arquivo.

## Operand stack

A stack possui:

    CLVM_STACK_MAX = 256

entries.

Cada entry é `int64_t`.

Mesmo opcodes originalmente pensados em 32 bits executam sobre uma 64-bit operand stack, exceto quando a semântica reduz explicitamente para 32 bits.

Overflow e required-pop underflow são faults.

## Comportamento de DROP

`DROP` é permissivo no interpreter atual:

- se houver valor, remove um;
- com stack vazia, não faz nada.

Isso difere de arithmetic, loads e calls que faultam quando faltam operands.

## Call stack

Return addresses usam stack separada de:

    CLVM_CALL_MAX = 64

entries.

Cada entry é um 32-bit code offset.

`CALL`, `CALL32`, `CALLI` e `CALLT` fazem push do return PC.

`RET` faz pop.

Overflow e underflow são faults explícitos.

## Estados da VM

Estados:

    READY
    RUNNING
    WAITING
    HALTED
    FAULTED

`clvm_step` muda READY para RUNNING durante um slice.

Quando o budget termina normalmente, volta a READY e retorna `CLVM_STEP_SLICE`.

WAITING produz yield sem executar.

HALTED e FAULTED permanecem terminal states até intervenção explícita do host.

## Resultados de step

Um slice retorna:

    CLVM_STEP_SLICE
    CLVM_STEP_YIELD
    CLVM_STEP_HALT
    CLVM_STEP_FAULT

O scheduler consegue assim distinguir time slicing, termination e failure.

## Contagem de instructions

Cada opcode obtido com sucesso incrementa:

    vm->executed

No kernel freestanding, o interpreter também verifica process scheduling periodicamente.

A cada 8192 instructions pode produzir yield se `proc_slice_due()` indicar expiração.

Safepoints e syscalls são outras scheduling boundaries.

## Mapa de opcodes

O espaço atual é contínuo de `0x00` a `0x47`.

### Stack e operações inteiras

| Opcode | Mnemonic | Immediate | Efeito |
|---:|---|---|---|
| 00 | NOP | — | nenhuma operação |
| 01 | PUSH | i32 | push de constant 32-bit sign-extended |
| 02 | ADD | — | soma 64-bit |
| 03 | SUB | — | subtração |
| 04 | MUL | — | multiplicação |
| 05 | DIV | — | divisão signed |
| 06 | DUP | — | duplica top |
| 07 | PRINT | — | pop para diagnostic print ring |
| 08 | HALT | — | halt |
| 0f | DROP | — | drop se houver valor |
| 10 | SWAP | — | troca top two |
| 11 | EQ | — | igualdade |
| 12 | LT | — | signed less-than |
| 14 | MOD | — | signed remainder |
| 15 | NE | — | desigualdade |
| 16 | LE | — | signed <= |
| 17 | GT | — | signed > |
| 18 | GE | — | signed >= |
| 19 | NEG | — | negation |
| 1d | UDIV | — | unsigned division |
| 1e | UMOD | — | unsigned remainder |
| 1f | ULT | — | unsigned < |
| 35 | AND | — | bitwise AND |
| 36 | OR | — | bitwise OR |
| 37 | XOR | — | bitwise XOR |
| 38 | SHL | — | left shift por count & 63 |
| 39 | SHR | — | logical right shift |
| 3a | SAR | — | arithmetic right shift |
| 3b | NOT | — | bitwise complement |
| 45 | ULE | — | unsigned <= |
| 46 | UGT | — | unsigned > |
| 47 | UGE | — | unsigned >= |

Binary ops fazem pop de `b`, depois `a`, e push de `a op b`.

## Faults de divisão

Signed e unsigned division/remainder faultam com divisor zero.

Signed `DIV` e `MOD` também faultam no caso:

    INT64_MIN / -1

evitando undefined behavior do host.

## Memory operations

| Opcode | Mnemonic | Largura |
|---:|---|---:|
| 0d | LOAD | 4 bytes |
| 0e | STORE | 4 bytes |
| 1a | LOADB | 1 byte |
| 1b | STOREB | 1 byte |
| 26 | LOAD64 | 8 bytes |
| 27 | STORE64 | 8 bytes |
| 28 | FLOAD | 4 bytes |
| 29 | FSTORE | 4 bytes |

Guest addresses são byte offsets na linear memory.

Endereço negativo, memory ausente ou range inválido produz `CLVM_FAULT_BAD_ADDRESS`.

Guest bytecode não dereferencia host pointers diretamente.

## Ordem de STORE

Nas stores o interpreter faz pop de:

1. address;
2. value.

Depois escreve value no address.

Code generators precisam seguir exatamente essa stack order.

## Linear memory

A VM expõe:

    memory[0 .. mem_size-1]

Ela pode ser owned pela própria VM ou anexada externamente com `clvm_vm_set_memory`.

Ao trocar a memory anexada, o owned flag é limpo e a allocation anterior pode ser liberada.

## Início do heap

O bump allocator escolhe o cursor inicial por memory size:

- pelo menos 16 MiB: 1 MiB;
- acima de 128 KiB: 64 KiB;
- caso contrário: metade da memory.

Assim uma região baixa permanece disponível para globals, strings e compiler static data.

## Guest allocation

`clvm_guest_malloc` usa bump allocation simples.

Cada chunk inclui prefix de oito bytes com size.

Allocation é alinhada a oito bytes.

`free` retorna sucesso, porém não recupera espaço.

`realloc` cria novo bloco e copia o payload anterior.

Logo o guest heap não é um allocator reclaiming geral.

## Control flow

As formas curtas usam signed 16-bit relative displacement:

    JMP
    JZ
    JNZ
    CALL

Formas longas usam signed 32-bit:

    JMP32
    JZ32
    JNZ32
    CALL32

O displacement é relativo ao PC **depois** do immediate.

Targets precisam satisfazer:

    0 <= target < code_size

Caso contrário ocorre `CLVM_FAULT_BAD_JUMP`.

## Conditional branches

`JZ` e `JZ32` fazem pop e saltam quando o valor é zero.

`JNZ` e `JNZ32` fazem pop e saltam quando é não zero.

A condition sempre é consumida.

## Calls indiretos e de tabela

`CALLI` recebe absolute code offset da operand stack.

Ele precisa estar dentro do code image.

`CALLT` contém um 32-bit absolute code offset como immediate.

Nesta revisão, `CALLT` atribui o PC após salvar return address sem range check explícito. Um target inválido falhará posteriormente no instruction fetch.

Esse detalhe altera a classificação do fault.

## Floating point

Floating ops usam IEEE-754 single-precision bit patterns nos 32 bits baixos de stack entries.

Instructions:

    FPUSH
    FLOAD
    FSTORE
    FADD
    FSUB
    FMUL
    FDIV
    FNEG
    FTOI
    ITOF
    FEQ
    FLT
    FLE

O runtime reinterpreta os 32 bits como C `float`.

Os resultados float retornam como bit pattern 32-bit dentro da stack de 64 bits.

## Float division

`FDIV` verifica se o divisor decodificado é `0.0f`.

Nesse caso usa o mesmo divide-by-zero fault dos inteiros.

A VM portanto não expõe infinity por float division by zero.

## Immediate 64-bit

`PUSH64` é opcode:

    0x25

seguido por eight-byte little-endian immediate.

O bit pattern é colocado como uma stack value de 64 bits.

## Instructions orientadas a IL

Há um grupo para higher-level IL/runtime:

    LDARG index:u8
    STLOC index:u8
    LDLOC index:u8
    NEWOBJ size:u32
    LDFLD offset:u32
    STFLD offset:u32
    CALLT target:u32
    LDSTR address:u32
    SAFEPOINT

Existem:

    16 IL argument slots
    32 IL local slots

Indexes inválidos entram na fault path de opcode inválido da implementação atual.

## Object operations

`NEWOBJ` aloca guest memory e retorna guest address.

Requested size zero vira 16 bytes.

`LDFLD` e `STFLD` usam object address + 32-bit field offset e operam em fields de oito bytes.

Não existe object-layout descriptor no instruction stream.

O layout de objects é uma convenção compiler/runtime sobre a linear memory.

## Safepoints

`SAFEPOINT` marca temporariamente:

    vm->safepoint = 1

e chama callback opcional do host.

Calls, allocation e syscalls também formam safepoint-like boundaries.

Isso permite integração com scheduler, GC e debugger sem colocar esses subsistemas no core do bytecode.

## Instruction SYS

`SYS` não possui immediate.

Ele faz pop de um valor e interpreta low 32 bits como syscall ID:

    id = pop()

Depois chama:

    vm->sys(vm, id, vm->sys_user)

Callback ausente ou retorno não zero causa:

    CLVM_FAULT_BAD_SYS

## Dono do syscall ABI

A VM core não define o significado de syscall 1, 50 ou 170.

Esses significados pertencem ao callback selecionado.

No ChrisOS o implementation canônico é:

    clvm_sys_dispatch()

Logo ele constitui o system-service ABI atual para CLVM hospedada pelo ChrisOS.

## Superfície atual de syscalls

Nesta revisão, `clvm_sys_dispatch` possui **173 numeric case IDs explícitos**.

A superfície cobre:

- 2D graphics/presentation;
- input, timing e sleep;
- 3D, camera, textures e voxels;
- filesystem I/O;
- guest allocation e nonlocal jumps;
- GC;
- threads, join, mutexes, conditions e TLS;
- sockets e DNS;
- checkpoint/hot reload;
- random e crypto;
- audio;
- privileged driver I/O, PCI e MMIO;
- outros platform/runtime services.

Os IDs estão como numeric `case` labels, não como um único enum público.

Isso é risco de ABI: mudar um número pode quebrar CLV já compilado.

## Syscall IDs representativos

| ID | Serviço |
|---:|---|
| 1 | put pixel |
| 2 | fill rectangle |
| 3 | line |
| 6 | clear surface |
| 10 | key state |
| 11 | current tick |
| 12 | sleep/wait |
| 13 | speaker tone |
| 30 | FPS estimate |
| 39 | viewport resize |
| 40 | viewport width |
| 41 | viewport height |
| 50 | file open |
| 51 | file close |
| 52 | file read |
| 53 | file write |
| 54 | file size/stat |
| 55 | file exists |
| 56 | guest malloc |
| 57 | guest free |
| 58 | setjmp |
| 59 | longjmp |
| 61 | guest realloc |
| 62 | thread create |
| 63 | thread join |
| 70 | GC allocation |
| 71 | GC collect |
| 127 | mutex lock |
| 128 | mutex unlock |
| 129 | condition wait |
| 130 | condition wake |
| 131 | TLS get |
| 132 | TLS set |
| 140–146 | socket/DNS |
| 150 | random u32 |
| 151 | SHA-256 |
| 152 | AES-128 block encrypt |
| 153 | X25519 |
| 160 | AC97 audio write |
| 170–175 | privileged low-level driver services |

A tabela é descritiva; o source de `clvm_sys_dispatch` é a referência operacional.

## Calling convention de syscalls

Arguments ficam na operand stack.

Cada handler faz pop em uma ordem específica.

Results normalmente são pushed de volta.

Um syscall também pode colocar a VM em WAITING, fazendo `SYS` produzir yield.

Portanto o ABI inclui stack shape e state transitions, não apenas IDs.

## Syscalls bloqueantes

Sleep, join, mutex/condition wait, socket receive e IRQ wait podem colocar a VM em WAITING.

Alguns handlers recolocam arguments e syscall ID na stack para retry após wakeup.

É um mecanismo cooperativo de continuation implementado acima do core opcode decoder.

## Thread model

O host ChrisOS pode criar child CLVM instances compartilhando:

- code;
- linear guest memory;
- syscall callback/context.

Cada child possui independentes:

- operand stack;
- call stack;
- PC;
- state;
- TLS.

Guest addresses portanto são comuns entre threads do mesmo slot porque apontam para a mesma memory.

## Identidade de synchronization

O helper define mutex identity como:

    (slot_id, guest_address)

O mesmo numeric address em dois application slots distintos não representa o mesmo mutex.

Isso evita cross-application synchronization acidental.

## TLS

Cada VM possui:

    16 TLS slots

de 64 bits.

Syscalls do kernel expõem get/set por índice.

TLS é per-VM/thread state, não parte da linear memory salvo quando software faz mirror explicitamente.

## setjmp/longjmp

O runtime oferece guest `setjmp` e `longjmp`.

O record salvo contém state como PC, operand-stack depth, call-stack depth e stack values.

O buffer reside na guest memory e precisa de range validation.

É um VM continuation format específico, não native C ABI `jmp_buf`.

## Fault model

Faults definidos:

    PC
    OPCODE
    TRUNCATED
    STACK_UNDERFLOW
    STACK_OVERFLOW
    CALL_UNDERFLOW
    CALL_OVERFLOW
    DIV_ZERO
    DIV_OVERFLOW
    BAD_ADDRESS
    BAD_JUMP
    BAD_SYS

Em fault:

    state = FAULTED
    fault = reason
    fault_pc = opcode PC

e step retorna `CLVM_STEP_FAULT`.

## Fault PC

`fault_pc` registra o PC do opcode em execução antes do fetch avançar o PC live.

Isso fornece localização estável para debugger.

## Operand truncado

Se o opcode existe mas seus immediate bytes passam do final do code, ocorre:

    CLVM_FAULT_TRUNCATED

Isso é diferente de tentar buscar opcode quando PC já está fora do code, que gera:

    CLVM_FAULT_PC

## Opcode desconhecido

Qualquer byte não tratado pelo switch atual gera:

    CLVM_FAULT_OPCODE

Apesar do range atual ser contínuo até `0x47`, extensões futuras precisam respeitar compatibility expectations de interpreters antigos.

## Contrato do assembler

ChrisAsm para CLVM converte textual mnemonics e labels em bytecode.

Bounds atuais:

    source <= 32768 bytes
    labels <= 128
    label name <= 24 bytes

São limites do assembler, não do file format CLV.

## Compiler pipeline

O ChrisC pipeline pode gerar CLVM bytecode e empacotar em image CLV.

Para programas pequenos ainda pode usar v1 quando code/entry cabem em 16 bits e não existe memory hint.

Caso contrário usa v2.

Portanto instalações atuais podem conter arquivos CLV v1 e v2 legitimamente.

## Relação com JIT

O JIT é backend alternativo para bytecode suportado.

Ele não redefine o formato CLV.

O interpreter permanece a referência semântica dos opcodes, salvo exceção documentada.

Syscalls JIT passam por trampoline com VM/context.

Executable JIT pages usam virtual range dedicado do kernel e teardown com TLB synchronization explícita.

## Security boundary

CLVM bytecode não é native machine code.

Ordinary guest memory accesses são range-checked.

System services só entram por syscall callback.

Entretanto o host ABI possui privileged driver operations protegidas por capability checks.

Portanto isolation depende de:

1. interpreter memory/control-flow validation;
2. capability enforcement correto no host.

Loader seguro não compensa syscall dispatcher permissivo.

## Fronteira de determinismo

Arithmetic, stack e linear-memory execution são em grande parte determinísticos para image e initial memory fixas.

Syscalls atravessam para time, input, filesystem, network, audio, graphics e hardware.

Testes de deterministic replay devem stubbar syscalls ou registrar external inputs.

## Requisitos de compatibilidade

Não podem mudar silenciosamente:

- CLVM magic;
- v1/v2 header layouts;
- little-endian encoding;
- checksum algorithm;
- opcode numbers;
- immediate widths;
- stack effects;
- branch displacement base;
- fault conditions;
- numeric syscall meanings publicados.

Mudança incompatível exige nova versão ou compatibility mechanism explícito.

## Limitações atuais

O design atual possui:

- sem ISA-version separada da container version;
- sem section table;
- sem distinção de static read-only data;
- sem code signing;
- sem per-function metadata no CLV;
- sem enum central de syscalls;
- operand/call stacks fixas;
- bump allocator com free não reclaiming;
- float semantics dependentes de C `float`;
- parity interpreter/JIT precisa ser validada continuamente.

São propriedades atuais, não garantias futuras.

## Próximos trabalhos de compatibilidade

Uma revisão futura deveria considerar:

1. versionamento separado para container e ISA;
2. syscall IDs centralizados;
3. opcode metadata machine-readable;
4. verifier pré-execução para branch targets e stack effects;
5. sections para static/read-only data;
6. float semantics explícitas;
7. capability manifest no executable;
8. deterministic syscall harness;
9. differential interpreter/JIT tests;
10. provenance metadata assinada ou hashada.

## Resumo de conformidade

Um loader/interpreter v2 conforme deve ao menos:

- ler o header v2 little-endian de 24 bytes;
- validar magic, flags, size, entry e FNV-1a;
- executar os opcodes com immediate widths e stack effects exatos;
- manter 64-bit operand stack e bounded call stack;
- range-check guest memory;
- validar branches de acordo com as regras atuais;
- entrar em FAULTED diante de execução inválida;
- tratar `SYS` como host callback boundary;
- preservar WAITING/HALTED/FAULTED para o scheduler.

## Nota de revisão

Esta especificação foi reconciliada contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

A distinção principal é que CLVM não é apenas uma lista de bytecodes: ela é um executável versionado, uma state machine precisa e um host ABI. Compatibilidade precisa considerar as três camadas em conjunto.
