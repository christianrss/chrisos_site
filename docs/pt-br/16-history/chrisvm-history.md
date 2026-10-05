---
id: chrisvm-history
lang: pt-br
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/boot.c
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/common/cpuid.c
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/buses/io.c
  - chrisvm/buses/mmio.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/frontend/main.c
  - chrisvm/frontend/view.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_machine_create
  - chris_load_elf
  - chris_boot
  - chris_run
  - chris_decode
  - chris_translate
  - chris_raise
  - chris_backend_by_name
depends_on:
  - architecture-history
related:
  - chrisvm-spec
  - chrisvm-boot-spec
  - chrisvm-chriscpu
  - chrisvm-machine
  - chrisvm-boot
  - emulator-paging
  - emulator-exceptions
  - virtualization-chrishv
---

# História do ChrisVM

## Escopo

ChrisVM é uma das linhas arquiteturais mais novas do ChrisOS.

Diferentemente de graphics ou do native toolchain, sua forma atual não emergiu de dezenas de refatorações visíveis. O Git mostra dois commits concentrados em 25 de setembro de 2026 que estabeleceram praticamente toda a foundation atual.

Este capítulo evita inventar uma longa evolução.

A sequência real foi:

1. criar uma virtual machine x86-64 in-process com CPU em software;
2. fazer direct boot de pequenos ELF lower-half;
3. validar CPU, memory, I/O e exceptions;
4. adicionar framebuffer guest e visualização host;
5. manter deliberadamente o path de produção ChrisOS/QEMU separado;
6. deixar hardware virtualization como backend seam futuro.

O source atual é reconciliado na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Por que ChrisVM foi uma nova branch arquitetural

Antes de ChrisVM, o ChrisOS já dependia fortemente de QEMU para validação do sistema.

QEMU fornecia uma plataforma virtual suficientemente rica para:

- boot firmware/bootloader;
- PCI;
- storage;
- networking;
- graphics;
- SMP;
- comportamento PC mais amplo.

ChrisVM não começou como drop-in replacement de QEMU.

Seu objetivo inicial era mais estreito:

> criar uma camada de virtual machine controlada pelo próprio projeto, em que ChrisOS define diretamente CPU state, instruction execution, memory translation e devices.

Essa distinção aparece explicitamente no primeiro commit.

## 25 de setembro de 2026 — surgem ChrisVM e ChrisCPU

Commit foundation:

    86f08da720c24ec6ee0b0179d6a97b3dbf0ca0f6

Mensagem:

    Add a ChrisCPU interpreter and the ChrisVM machine foundation. (#17)

O commit adicionou cerca de 4.777 linhas e criou quase toda a estrutura atual.

Incluiu:

- API pública ChrisVM;
- architectural CPU state compartilhado;
- machine config/ownership;
- direct ELF boot;
- ChrisCPU interpreter;
- x86-64 decoder/executor;
- flags;
- operands;
- four-level MMU;
- exception delivery;
- CPUID determinístico;
- port-I/O bus;
- MMIO bus;
- serial device;
- trace/debug;
- frontend CLI;
- arithmetic guest;
- tests;
- seam ChrisHV.

É por isso que a história do ChrisVM é concentrada: muitas decisões arquiteturais chegaram juntas.

## Machine e CPU já nasceram separadas

O primeiro commit não tratou o interpreter como se ele fosse toda a VM.

Separou:

    ChrisMachine
        possui RAM e devices

    ChrisArchitectureState
        possui CPU state guest-visible

    ChrisCpuBackend
        executa esse state

    ChrisCPU
        backend em software

    ChrisHV
        backend reservado para hardware assistance

Essa separação continua sendo uma das decisões mais fortes do subsistema.

CPU execution pode evoluir sem redefinir ownership de RAM/devices.

## Shared architecture state desde o início

O primeiro `chris_arch.h` já continha um state amplo:

- GPRs;
- RIP/RFLAGS;
- control registers;
- segments;
- descriptor tables;
- EFER/MSR-related state;
- TSC;
- XMM storage;
- CPL.

Nem todo field implicava suporte completo de instructions.

O ponto histórico é que o backend boundary foi desenhado em torno de **architectural state**, não de variáveis privadas do interpreter.

Isso deixa um caminho conceitual para hardware virtualization futura.

## ChrisHV nasceu propositalmente não funcional

O primeiro commit adicionou:

    chrisvm/cpu/hv/chrishv.c

e placeholders VMX/SVM.

Mas a mensagem dizia explicitamente:

> ChrisHV is only a refused backend.

O source atual mantém isso.

Selecionar ChrisHV resolve um backend object, porém initialization falha deliberadamente porque VMX/SVM/KVM execution não existe.

Logo ChrisHV surgiu como **architectural seam**, não como acceleration parcial.

## QEMU permaneceu

O mesmo commit declarou:

> the QEMU kernel path stays in place.

Essa frase define a relação entre ChrisVM e QEMU desde o nascimento.

ChrisVM não invalidava os gates QEMU.

Ele era um ambiente controlado para assumir ownership de mais partes da virtual hardware stack.

## Direct ELF boot em vez de firmware emulation

O primeiro ChrisVM não emulava:

- BIOS;
- UEFI;
- Limine;
- x86 reset vector;
- firmware discovery.

Usava direct ELF loading.

O host:

1. lê ELF64;
2. copia PT_LOAD para RAM guest;
3. cria estado mínimo de long mode;
4. cria identity page tables;
5. define RIP/RSP;
6. inicia execução interpretada.

Isso reduziu bastante o initial scope.

## Por que direct boot foi uma simplificação estratégica

Um full PC boot exigiria resolver muitos subsistemas antes de testar uma instruction.

Direct boot permitiu validar cedo:

- decoder;
- arithmetic;
- stack/control flow;
- paging;
- exceptions;
- port I/O;
- serial;
- shutdown.

Assim ChrisCPU podia ser testado independentemente de firmware e PCI.

## Boot protocol v1 era lower-half por design

O atual `chrisvm-boot-spec` registra protocol v1.

O loader coloca PT_LOAD em `p_vaddr` e constrói identity mappings.

Higher-half segments são rejeitados.

Essa restriction não surgiu depois como regressão.

Ela faz parte da simplificação original.

## Consequência: kernel ChrisOS de produção não era guest válido

O kernel de produção é higher-half e depende de boot-information contract mais rico.

Assim o ChrisVM inicial não podia simplesmente carregar o ELF normal do kernel.

Isso era intencional.

A frase histórica correta é:

> ChrisVM bootava guests ELF diretos construídos para ele, mas não o kernel ChrisOS de produção.

Essa boundary continua no segundo commit.

## Arithmetic guest como prova executável

O primeiro commit incluiu um pequeno guest em assembly.

Seu papel era testar o interpreter, não provar um sistema operacional completo.

O guest cobria:

- serial output;
- integer arithmetic;
- memory access;
- call/return;
- HLT.

Os tests verificavam register result e serial text.

Isso reduz ambiguidade de falhas.

## Determinismo desde o começo

ChrisCPU evitava repassar CPUID do host.

Usava CPUID definido pelo projeto.

O virtual TSC avançava deterministicamente junto com instructions interpretadas.

O frontend também usava explicit step limits.

Essas escolhas reduzem variação por host.

Não criam full record/replay, mas fortalecem tests reproduzíveis.

## Decoder x86 bounded

O decoder inicial já era substancial, mas não completo.

A arquitetura separava:

- decode;
- operands;
- execute;
- flags;
- MMU;
- exceptions.

Isso tornava missing instruction forms explícitas.

Unsupported encoding podia virar `#UD`/decode failure em vez de depender acidentalmente do host.

## Four-level paging na foundation

`mmu.c` entrou no primeiro commit.

Já modelava:

    PML4
      -> PDPT
          -> PD
              -> PT

com large pages.

ChrisVM portanto não começou como simple flat-address emulator.

Ele foi desenhado em torno de guest-visible x86 paging desde a foundation.

## Exception delivery também nasceu junto

`exceptions.c` também entrou no primeiro commit.

A VM distinguia:

- monitor-visible exception quando guest não tinha IDT;
- guest IDT delivery;
- tentativa de double fault;
- triple-fault termination.

Assim guest errors não precisavam abortar o host process.

## Port I/O e MMIO separados

O first commit criou:

    chrisvm/buses/io.c
    chrisvm/buses/mmio.c

A separação segue a estrutura x86 real.

Port I/O usa IN/OUT.

MMIO passa por physical memory access.

Isso evita hard-code de devices dentro do CPU executor.

## Serial foi o primeiro device real

A machine incluiu uma serial simples 16550-like em COM1.

É um ótimo first device porque oferece:

- guest output observável;
- port I/O;
- register semantics;
- loopback test;
- sem DMA complexo.

Assim ChrisVM possuía external behavior channel antes de graphics.

## Trace já fazia parte da foundation

O primeiro commit também adicionou instruction trace.

O sistema atual mantém ring com RIP/bytes/formatted instruction.

Isso ajuda especialmente em failures graves de exception delivery.

Debugging não ficou para "depois que o interpreter funcionasse".

Já era parte da foundation.

## Tests vieram junto com a arquitetura

O commit foundation incluiu um host test file substancial.

Isso importa porque ChrisVM não nasceu como demo visual.

Os tests cobriam:

- flags;
- arithmetic;
- memory;
- control flow;
- I/O;
- exceptions;
- CPUID/MSR;
- malformed ELF;
- ChrisHV rejection;
- decoder fuzz.

Testability foi parte do design inicial.

## Menos de uma hora depois — framebuffer

Segundo commit principal:

    be4307a28afb9b923549243d0f85a7358fcbf1b2

Mensagem:

    Draw the boot splash on the ChrisVM framebuffer.

Foi adicionado:

- framebuffer device;
- host viewer;
- splash guest;
- mais decode/execute support;
- mais tests;
- integração framebuffer em machine/boot.

É a única grande extensão estrutural do ChrisVM no Git atual.

## Fixed framebuffer

A base física ficou em:

    0x02000000

com:

    640 x 480
    32 bits per pixel

O guest escreve diretamente em linear framebuffer memory.

O host pode:

- inspecionar pixels;
- dump PNG/PPM;
- mostrar em SDL quando disponível.

Isso gerou o primeiro guest visual sem modelar GPU.

## REP STOS expande CPU por necessidade concreta

O splash guest preenche framebuffer usando `REP STOS`.

O commit então ampliou decode/execute para suportar esse workload.

É um pattern normal de emulator development:

    guest pequeno
        |
        v
    instruction faltante aparece
        |
        v
    implementar/testar subset necessário
        |
        v
    deixar unsupported explícito

Melhor que alegar ISA completa prematuramente.

## Host visualization ficou fora da guest architecture

SDL viewer não virou GPU guest.

O guest vê linear framebuffer.

O host decide como apresentar.

Separação:

    guest contract:
        memory-backed framebuffer

    host convenience:
        PNG/PPM/SDL

Isso deixa espaço para future device models.

## O kernel de produção continuou rejeitado

O segundo commit diz explicitamente:

> The ChrisOS kernel ELF stays rejected.

Esse é um dos fatos históricos mais importantes.

Mesmo com splash visível, ChrisVM não passou a alegar boot de production kernel.

Graphics success não removeu limitations do lower-half/direct boot.

## Dois commits definem quase todo o structure atual

O path history mostra apenas esses dois commits para grande parte do subsystem.

Exemplos:

- `chriscpu.c`: só foundation;
- `mmu.c`: só foundation;
- `exceptions.c`: só foundation;
- `chrishv.c`: só foundation;
- `machine.c`: foundation + framebuffer;
- `boot.c`: foundation + framebuffer;
- `decode.c`: foundation + framebuffer;
- `test_chrisvm.c`: foundation + framebuffer.

Por isso esse capítulo possui menos phases que graphics/toolchain history.

## Arquitetura atual ainda reflete o split original

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`:

    guest ELF
       |
       v
    ChrisMachine
       |
       +-- RAM
       +-- I/O bus
       +-- MMIO bus
       +-- serial
       +-- framebuffer
       |
       v
    ChrisArchitectureState
       |
       v
    ChrisCPU

ChrisHV permanece reservado/refused.

A foundation ficou estável.

## Machine atual continua pequena

ChrisVM ainda não emula toda a plataforma exigida pelo kernel de produção.

Faltam áreas importantes:

- UEFI/BIOS/Limine;
- full PCI topology;
- ACPI;
- APIC/IOAPIC platform;
- storage controllers;
- production network devices;
- USB host stack;
- SMP completo;
- GPU device path completo;
- hardware-assisted CPU backend.

Isso é consistente com o objetivo original.

## Boot protocol atual continua direct v1

O boot code atual ainda:

- aceita ELF64 x86-64;
- carrega lower-half PT_LOAD;
- cria identity mapping;
- entra diretamente em long mode;
- inicia CPL0;
- não cria Limine handoff normal.

A limitation histórica continua sendo compatibility boundary atual.

## ChrisVM versus QEMU

Os dois sistemas resolvem camadas diferentes.

### QEMU

Adequado para validar ChrisOS contra uma PC-like platform mais rica com devices/firmware existentes.

### ChrisVM

Adequado para controlar/testar diretamente:

- CPU state model;
- decoder;
- execution semantics;
- page translation;
- exceptions;
- simple devices;
- deterministic host tests.

ChrisVM pode crescer futuramente, mas não é hoje substituto geral de QEMU.

## ChrisCPU versus ChrisHV

O seam prevê:

    shared architecture state
       /               \
      v                 v
  ChrisCPU          ChrisHV
 software           hardware-assisted

Só o path esquerdo existe.

Ter o direito no source força consideration de backend boundary cedo, mas não equivale a acceleration support.

## Decoder fuzzing fortalece a evidência

A suite atual inclui deterministic decode fuzz.

Random byte strings entram no decoder e successful decodes precisam ter legal bounded length.

Isso é útil porque x86 decoding é parser surface de risco alto.

Não prova ISA conformance, mas melhora malformed-input robustness.

## Malformed ELF protege o host boundary

Direct boot exige host-side ELF parsing.

Logo loader é trust boundary.

Tests rejeitam malformed images em vez de copiar offsets arbitrários para guest RAM.

Direct boot simplificou machine, mas colocou mais responsabilidade no loader.

## Exit reasons formalizam outcomes

A API distingue:

- HLT;
- shutdown;
- exception;
- triple fault;
- breakpoint;
- step limit;
- unmapped access.

Isso permite distinguir:

    guest stop intencional

de:

    fault/limit condition

sem derrubar host process.

## Debugger continua monitor-oriented

Breakpoints são monitor RIP breakpoints, não full DR0–DR7 model.

Trace ring é host diagnostic state.

Isso segue o objetivo original de development emulator, não transparent hypervisor.

## Milestones históricos

| Data | Commit | Significado |
|---|---|---|
| 2026-09-25 21:28 UTC | `86f08da` | machine, ChrisCPU, paging, exceptions, buses, serial, direct ELF boot e tests |
| 2026-09-25 22:25 UTC | `be4307a` | linear framebuffer, splash guest, PNG/SDL e suporte extra de execution |

A cronologia curta é um dado importante.

ChrisVM nasceu como subsystem coerente, não como acumulação longa de experiments desconectados.

## O que não aconteceu

Claims tentadores mas falsos na revisão analisada:

- ChrisVM não substituiu QEMU;
- ChrisVM não bootou production ChrisOS kernel;
- ChrisHV não ficou funcional;
- framebuffer não virou GPU model;
- paging não tornou interpreter x86-64 completo;
- XMM storage não implica SSE;
- CPUID state não significa host CPUID passthrough.

Source e commit messages deixam esses non-claims claros.

## Lições arquiteturais

### Comece com subset executável

Direct-boot guest pequeno tornou CPU/MMU testável antes de firmware completeness.

### Separe machine ownership de CPU execution

Isso criou backend seam limpo.

### Adicione tests junto com implementation

ChrisVM nasceu host-testable.

### Recuse unsupported backend explicitamente

Backend que falha claramente é melhor que um que finge acceleration.

### Output visual não prova platform compatibility

Splash provou framebuffer/instructions, não production kernel boot.

## Maturity statement atual

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, ChrisVM é melhor descrito como:

> uma virtual machine x86-64-subset determinística, single-vCPU e host-testable, com direct ELF boot, four-level paging, exceptions, serial, port I/O, MMIO e fixed framebuffer.

Ainda não é:

> um PC virtualizer completo capaz de substituir QEMU no boot de produção do ChrisOS.

A história sustenta essa distinção desde o primeiro commit.

## Próximos boundaries históricos

Uma nova entrada neste capítulo será relevante quando ChrisVM cruzar boundary real, por exemplo:

- production kernel boot;
- higher-half/boot-information protocol v2;
- functional PCI topology;
- SMP;
- ChrisHV funcional;
- hardware-assisted execution;
- stable disk/network device model;
- replacement de algum QEMU validation class.

Pequenas adições de opcodes pertencem mais à implementation documentation que à architecture history.

## Nota de revisão

Este capítulo foi reconciliado contra a revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` e os dois commits foundation listados.

O fato histórico central é a estabilidade de intenção: ChrisVM nasceu como emulator controlado e testável ao lado de QEMU, e o source atual ainda preserva essa boundary.
