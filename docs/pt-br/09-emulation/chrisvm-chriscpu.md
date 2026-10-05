---
id: chrisvm-chriscpu
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/machine.h
  - chrisvm/machine/boot.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/cpu/common/cpuid.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_machine_create
  - chris_load_elf
  - chris_boot
  - chris_run
  - chris_decode
  - chris_execute
  - chris_translate
  - chris_raise
  - chris_cpuid
depends_on:
  - emulator-theory
  - x86-64-memory-privilege
related:
  - chrisvm-machine
  - chrisvm-boot
  - emulator-paging
  - emulator-exceptions
  - virtualization-chrishv
  - chrisvm-spec
---

# ChrisVM e ChrisCPU

## Escopo

ChrisVM é a máquina virtual e plataforma controlada pelo próprio projeto. ChrisCPU é o backend de execução x86-64 em software.

São abstrações separadas.

ChrisVM possui a máquina guest: RAM, registros de port I/O e MMIO, serial, framebuffer, configuração, estado de boot e backend de CPU ativo. ChrisCPU executa instructions x86-64 guest sobre um estado arquitetural compartilhado.

A separação central é:

~~~text
guest program
    |
    v
ChrisMachine
    |
    +-- RAM
    +-- port I/O
    +-- MMIO
    +-- serial
    +-- framebuffer
    |
    v
ChrisArchitectureState
    |
    v
ChrisCpuBackend
    |
    +-- ChrisCPU   interpreter implementado
    |
    +-- ChrisHV    reservado, atualmente recusado
~~~

Um futuro backend hardware-assisted deve executar o mesmo machine contract em vez de criar uma segunda plataforma virtual.

## Configuração da máquina

`ChrisConfig` controla o machine model no host.

Defaults atuais:

| Configuração | Default |
|---|---:|
| RAM | 16 MiB |
| backend | `chriscpu` |
| modo determinístico | habilitado |
| máximo de steps | 1.000.000 |
| tracing | desabilitado |
| framebuffer dump | desabilitado |

A criação rejeita RAM menor que 2 MiB ou que não seja múltipla de 2 MiB.

Isso se relaciona com o boot atual, que constrói mappings iniciais usando páginas de 2 MiB.

O default pequeno é intencional: ChrisVM é hoje emulator de desenvolvimento, não target de compatibilidade PC completa.

## Ownership e lifetime

`chris_machine_create()` segue esta sequência:

1. inicializa/copia configuração;
2. resolve backend;
3. inicializa backend;
4. aloca RAM guest zerada;
5. conecta serial;
6. conecta framebuffer;
7. cria CPU 0.

Failure em cada etapa libera os recursos já adquiridos.

`chris_machine_destroy()` encerra o backend e libera CPU, framebuffer, RAM e machine object.

O backend de CPU não é owner da plataforma; ele executa contra recursos pertencentes a `ChrisMachine`.

## Estruturas bounded

O machine model atual possui limites fixos importantes:

| Estrutura | Limite |
|---|---:|
| registros port-I/O | 8 |
| registros MMIO | 8 |
| trace ring | 256 entries |
| captura TX serial | 8192 bytes |
| CPUs no path atual | 1 |

São limites da implementação, não limites da arquitetura x86.

## Estado arquitetural compartilhado

`ChrisArchitectureState` contém:

- 16 GPRs de 64 bits;
- RIP/RFLAGS;
- CR0, CR2, CR3, CR4, CR8;
- CS, DS, ES, FS, GS, SS;
- TR e LDTR;
- GDTR e IDTR;
- EFER;
- STAR/LSTAR/CSTAR/FMASK;
- FS/GS/kernel-GS bases;
- APIC base;
- TSC virtual;
- storage para 16 XMM registers;
- CPL.

A presença de field não prova suporte completo à facility.

XMM storage existe, por exemplo, mas CPUID não anuncia SSE.

O objetivo é ter um único contrato de CPU compartilhado por backends.

## Backend contract

`ChrisCpuBackend` define operações para:

- init;
- create CPU;
- reset;
- run;
- IRQ injection;
- export/import de state;
- TLB invalidation;
- shutdown.

ChrisCPU implementa esse contrato em software.

ChrisHV aparece no mesmo seam, mas continua propositalmente não funcional.

A arquitetura possui um backend boundary sem alegar dois backends operacionais.

## Boot model

Boot protocol v1 não emula o boot PC completo.

Não executa:

- reset firmware;
- BIOS;
- UEFI;
- Limine.

O host carrega um ELF64 restrito em RAM e chama `chris_boot()`.

O boot instala estado suficiente para iniciar guest 64-bit diretamente:

- GDT;
- page tables;
- CR0/CR3/CR4;
- EFER;
- stack;
- segments;
- framebuffer mapping;
- CPL 0.

O kernel higher-half de produção ainda está fora desse contrato.

## RAM e framebuffer

Guest RAM é memória host alocada e zerada.

`chris_write_ram()` e `chris_read_ram()` passam pela camada de physical access.

O framebuffer fixo usa:

- base física `0x02000000`;
- 640 × 480;
- 32 bpp.

É framebuffer simples, não device VirtIO-GPU.

Guest escreve na região mapeada e host tooling pode inspecionar ou mostrar os pixels.

## Instruction fetch

ChrisCPU busca no máximo 15 bytes a partir de RIP, porque instruction x86 possui limite de 15 bytes.

Cada byte passa por virtual-memory translation com access type de execução.

O interpreter não pode ignorar paging apenas por rodar no host.

Fault em instruction fetch participa da mesma machinery de guest faults.

## Decode

`chris_decode()` transforma bytes em `ChrisInsn`.

O structure registra, entre outros:

- operand size;
- address size;
- REX;
- ModRM/SIB;
- displacement;
- immediate;
- condition code;
- ALU operation;
- LOCK/REP;
- metadata específica da instruction form.

O decoder implementa subset deliberado de x86-64.

Encoding não suportado não deve cair em comportamento arbitrário do host; é rejeitado ou convertido em invalid-opcode guest behavior.

## Execution loop

O core loop segue:

~~~text
check breakpoint
    |
fetch
    |
decode
    |
format/trace
    |
clear rip_dirty
    |
execute
    |
se RIP não foi alterado explicitamente:
    RIP += instruction length
    |
advance counters/virtual time
    |
consider pending interrupt
~~~

`rip_dirty` é invariante importante.

Branches, calls, returns e exceptions que escrevem RIP marcam essa condição para impedir que o generic path some também o tamanho da instruction.

## Step limit

Execution é bounded por `max_steps`.

Guest em infinite loop pode terminar como:

    CHRIS_EXIT_STEP_LIMIT

em vez de prender o host em interpreter loop infinito.

É safety bound do emulator, não x86 exception.

## Exit reasons

A API distingue:

- HLT;
- shutdown;
- exception;
- triple fault;
- breakpoint;
- step limit;
- unmapped physical access.

"Execution stopped" portanto não é um único estado.

Tests podem validar exatamente por que o guest parou.

## Virtual address translation

`chris_translate()` implementa four-level x86-64 paging:

~~~text
CR3
 |
 v
PML4
 |
 v
PDPT
 |
 v
PD
 |
 v
PT
~~~

Também reconhece large pages de 1 GiB e 2 MiB.

Uma translation 4 KiB pode exigir até quatro PTE reads.

Sem TLB modelado como cache efetivo nesse path, memória interpretada custa significativamente mais que acesso direto a array host.

## Permission checks

A translation verifica:

- present;
- writable;
- user/supervisor;
- CR0.WP;
- NX com EFER.NXE;
- canonical addresses.

Também atualiza accessed/dirty bits quando aplicável.

Virtual address não canônico é tratado como general-protection path, não como simples page-not-present.

## Cross-page accesses

`chris_va_read()` e `chris_va_write()` quebram operações em boundaries de 4 KiB.

Assim um guest load/store que atravessa page boundary precisa de múltiplas translations.

Isso preserva permission semantics por página.

## Page fault state

Quando translation produz page fault:

- CR2 recebe endereço virtual;
- error code é composto;
- `chris_raise()` recebe vector 14.

Se page table aponta para backing físico inexistente, emulator pode encerrar com `CHRIS_EXIT_UNMAPPED` em vez de inventar guest page fault para memória host inexistente.

## Exception delivery

`chris_raise()` tenta entregar exception ao guest.

Sem IDT instalada, a exception vira monitor-visible:

    CHRIS_EXIT_EXCEPTION

com vector/error preservados.

Com IDT válida, ChrisCPU lê gate, valida, constrói frame na guest stack, carrega code segment e transfere RIP.

Se a entrega falha, tenta double fault.

Nova falha resulta em:

    CHRIS_EXIT_TRIPLE

e dump do trace ring.

Isso diferencia guest exception normal de colapso da própria exception machinery.

## Interrupt injection

O backend contract contém IRQ injection.

ChrisCPU armazena pending vector e entrega quando IF permite.

O código também modela o delay de uma instruction após STI.

Mesmo assim, o machine model atual é single-vCPU e não possui a plataforma completa de timer/APIC/IOAPIC do kernel de produção.

CPU interrupt logic não equivale a PC interrupt platform completa.

## CPUID determinístico

`chris_cpuid()` não repassa host CPUID.

Leaf 0 expõe:

    ChrisCPU    

Leaf 1 anuncia subset pequeno, incluindo TSC, MSR, CMOV, APIC e PSE relacionados.

FPU e SSE não são anunciados.

Extended leaf anuncia long mode; SYSCALL não é anunciado porque execution não está implementada, apesar de existir state relacionado em EFER.

Invariante:

> guest capability discovery não deve anunciar facility que o backend não consegue executar.

## Tempo determinístico

O state possui TSC virtual.

ChrisCPU avança tempo virtual junto com execution interpretada em vez de usar timing não controlado do host como primary clock.

Isso aumenta reproducibility.

Não é full deterministic replay; external inputs e future devices exigiriam event recording adicional.

## Debug e trace

Cada CPU mantém trace ring de 256 instructions.

Entry registra:

- RIP;
- instruction length;
- até 15 raw bytes;
- texto formatado.

Frontend também pode parar em breakpoint de RIP.

São monitor facilities, não implementação completa dos x86 debug registers.

## Complexidade e performance

ChrisCPU é interpreter.

Para (N) guest instructions:

[
T(N) = O(N cdot (D + E + M))
]

onde:

- (D) é decode;
- (E) é execution;
- (M) é memory translation/device work.

Workloads memory-heavy podem ser caros porque cada access pode disparar page walk.

O objetivo atual é correctness, inspectability e tests controlados, não near-native throughput.

Hardware-assisted execution pertence ao futuro ChrisHV.

## Evidência de validação

`chrisvm/tests/test_chrisvm.c` possui cases nomeados para:

- arithmetic flags;
- CPU ADD;
- memory + CALL/RET;
- serial/ports;
- faults;
- CPUID/MSR;
- multiply/divide;
- ELF accept/reject;
- decoder fuzz;
- real MMIO callbacks;
- STOS/framebuffer splash.

Fault tests cobrem invalid opcode, page fault, general protection, divide error e step-limit.

O page-fault test verifica CR2.

São host tests do ChrisVM, não conformance proof completa de x86-64.

## Decoder fuzzing

A suite fornece byte strings pseudo-random determinísticas a `chris_decode()`.

Decode aceito precisa ter instruction length legal e bounded.

Isso melhora robustez do parser x86.

Não prova semantic correctness de toda instruction aceita.

## Security boundary

ChrisVM executa guest state dentro do próprio host process.

Deve ser tratado como experimental emulation code, não hardened sandbox para binary hostil.

Bounds, explicit translation, malformed-ELF tests e fuzzing reduzem risco acidental, mas não estabelecem isolation formal entre malicious guest e host.

## Guest state versus host state

Registers, page tables, exceptions e device-visible values pertencem ao estado guest modelado. Ponteiros de `calloc`, buffers internos, callbacks e estruturas C pertencem ao host process. O emulator precisa manter essa fronteira: guest physical address nunca deve ser tratado como host pointer bruto. Toda passagem entre os domínios deve ocorrer pelas rotinas de physical/virtual access e pelos device callbacks declarados.

## Concurrency model

O machine path atual cria somente CPU 0.

Não existe multiprocessor execution em que várias host threads alterem a mesma `ChrisMachine`.

Por isso ainda não há o conjunto de synchronization rules exigido por multi-vCPU.

SMP futuro precisaria definir:

- shared RAM ordering;
- interrupt routing;
- guest atomic operations;
- device concurrency;
- CPU lifecycle;
- deterministic scheduling.

## Limitações atuais

ChrisVM/ChrisCPU não fornece atualmente:

- boot do production ChrisOS kernel;
- execução de UEFI/BIOS/Limine;
- ISA x86-64 completa;
- ChrisHV funcional;
- PCI completo;
- mature VirtIO devices;
- timer/APIC/IOAPIC suficientes ao kernel real;
- SMP;
- production storage/network;
- GPU model completo;
- hardened hostile-guest isolation.

Essa é a boundary entre development emulator atual e PC virtualizer geral.

## Papel arquitetural

ChrisVM funciona hoje como laboratório de execução controlado pelo projeto.

Permite testar:

- CPU state;
- decoding;
- flags;
- paging;
- exception delivery;
- I/O e MMIO;
- simple devices;
- direct boot.

QEMU continua sendo environment de integração mais amplo para o OS de produção.

Os dois são complementares, não intercambiáveis.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

A descrição correta é: máquina determinística, single-vCPU, com subset x86-64 interpretado em software, direct ELF boot e fault/device models explícitos. Não deve ser descrita como PC emulator completo nem como hypervisor hardware-accelerated.
