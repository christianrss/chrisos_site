---
id: chrisvm-spec
lang: pt-br
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/config.c
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
  - chrisvm/debug/trace.c
  - chrisvm/frontend/main.c
  - chrisvm/tests/test_chrisvm.c
  - chrisvm/Makefile
symbols:
  - chris_config_init
  - chris_machine_create
  - chris_machine_destroy
  - chris_backend_by_name
  - chris_run
  - chris_decode
  - chris_translate
  - chris_raise
  - chris_cpuid
  - chris_io_map
  - chris_mmio_map
depends_on:
  - specifications-policy
  - chrisvm-chriscpu
  - chris-architecture-state
  - chrisvm-machine
related:
  - chrisvm-boot-spec
  - emulator-theory
  - emulator-paging
  - emulator-exceptions
  - virtualization-chrishv
---

# Especificação do ChrisVM

## Status e fronteira de conformidade

Este documento especifica o contrato visível ao guest e ao host implementado pelo ChrisVM na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` do ChrisOS.

É uma especificação de implementação presa à revisão, não uma afirmação de compatibilidade completa com um PC x86-64.

Uma implementação conforme a esta revisão reproduz o comportamento descrito aqui para o subset implementado. Comportamento existente em hardware x86-64 real, mas ausente no source atual, está fora do contrato.

O backend executável atual é o **ChrisCPU**, um interpreter em software. O **ChrisHV** existe somente como seam de interface e falha intencionalmente na initialization porque VMX, SVM e KVM não estão implementados nesta revisão.

## Separação arquitetural

ChrisVM é a máquina/plataforma virtual.

ChrisCPU é um backend de execução da CPU.

A arquitetura é:

    guest
      |
      v
    ChrisArchitectureState
      |
      +-- ChrisCPU interpreter
      |
      +-- ChrisHV seam (não funcional)
      |
      v
    ChrisMachine
      +-- RAM
      +-- barramento de port I/O
      +-- barramento MMIO
      +-- serial
      +-- framebuffer
      +-- shutdown port

O CPU backend não possui a plataforma virtual.

A machine possui RAM e devices. O backend executa o estado arquitetural compartilhado contra essa machine.

## Objeto de configuração

Os campos públicos de `ChrisConfig` são:

| Campo | Significado |
|---|---|
| `ram_size` | tamanho da RAM guest |
| `backend` | nome do CPU backend |
| `trace` | trace de instruções |
| `trace_memory` | chave de memory tracing |
| `trace_io` | trace de port I/O |
| `trace_mmio` | trace MMIO |
| `deterministic` | policy flag de execução determinística |
| `max_steps` | budget máximo de steps |
| `break_rip` | endereço de breakpoint |
| `has_break` | breakpoint habilitado |
| `debug` | debugger interativo |
| `headless` | suprime viewer do framebuffer |
| `fb_dump` | caminho para dump do framebuffer |

`chris_config_init` define:

    ram_size = 16 MiB
    backend = "chriscpu"
    deterministic = 1
    max_steps = 1.000.000

Os demais campos começam zerados.

O parser atual de command line expõe backend, tracing, deterministic mode, debugger/headless, breakpoint, framebuffer dump e max-step. `ram_size` permanece um campo de API, não uma opção normal do frontend.

## Restrições de criação

`chris_machine_create` rejeita RAM menor que 2 MiB.

A RAM também precisa estar alinhada a 2 MiB:

[
ram_size mod 2MiB = 0
]

O framebuffer fica fixo em:

    0x02000000

ou 32 MiB.

`chris_fb_attach` rejeita machine cuja RAM ultrapasse essa base. Na topologia completa atual, o limite efetivo de RAM é portanto 32 MiB enquanto o framebuffer fixo está presente.

O default de 16 MiB satisfaz a restrição.

## Limites internos da machine

Os limites atuais são:

    CHRIS_IO_MAX     = 8
    CHRIS_MMIO_MAX   = 8
    CHRIS_TRACE_RING = 256
    CHRIS_TX_MAX     = 8192

São limites de implementação, não limites arquiteturais do x86.

Device model que precise de mais de oito ranges de port ou MMIO exige alteração das tabelas internas.

## Quantidade de CPUs

A machine atual cria exatamente uma CPU:

    backend->create_cpu(machine, 0)

Não existe topologia SMP, AP startup, local APIC timer ou fabric de IPI na machine atual.

O estado compartilhado permite evolução futura, mas esta revisão é single-vCPU.

## Estado arquitetural compartilhado

`ChrisArchitectureState` é o contrato canônico trocado pelo backend.

Inclui:

- 16 general-purpose registers;
- RIP;
- RFLAGS;
- CR0, CR2, CR3, CR4, CR8;
- CS, DS, ES, FS, GS, SS;
- placeholders TR/LDTR;
- GDTR e IDTR;
- EFER;
- STAR, LSTAR, CSTAR e FMASK;
- bases FS/GS/KERNEL_GS;
- APIC base;
- TSC virtual;
- 16 slots XMM;
- CPL.

A existência de um campo não implica suporte completo à facility.

Por exemplo, há storage XMM no state comum, mas CPUID não anuncia SSE nesta revisão.

## Interface de backend

`ChrisCpuBackend` fornece:

    init
    create_cpu
    reset
    run
    inject_irq
    get_state
    set_state
    invalidate_tlb
    shutdown

A intenção é que mecanismos alternativos importem/exportem o mesmo state.

É um seam de compatibilidade, não prova de que toda tradução futura para VMCS/VMCB já esteja resolvida.

## Estado do ChrisHV

Selecionar:

    backend = "chrishv"

resolve o objeto `chrishv_backend`.

Sua initialization retorna falha e informa que VMX/SVM não estão implementados.

A suite confirma explicitamente que a criação da machine com esse backend falha.

O status normativo é:

    chriscpu: implementado
    chrishv: reservado, não funcional

Nenhum frontend ou documento deve tratar ChrisHV como acceleration backend disponível nesta revisão.

## Loop de execução do ChrisCPU

Para cada step o ChrisCPU:

1. testa breakpoint em RIP;
2. busca até 15 bytes via guest virtual memory;
3. decodifica uma instrução;
4. grava trace;
5. executa a operação;
6. avança RIP quando a instrução não o modificou explicitamente;
7. verifica pending IRQ;
8. incrementa step counter;
9. incrementa TSC virtual em um.

O TSC avança uma vez por instrução interpretada.

É accounting determinístico, não modelo de ciclos físicos.

## Fetch de instrução

O helper atual busca 15 bytes, um por vez, com `chris_va_read` usando acesso de execução.

Quinze bytes é o limite arquitetural do x86.

Como todos os 15 bytes são buscados antes do decode, uma instrução curta perto do fim de uma mapping pode causar acesso a bytes que não pertencem à instrução.

É uma limitação de precisão da implementação atual.

## Contrato do decoder

`chris_decode` recebe:

    byte buffer
    comprimento disponível
    ChrisInsn de saída

Sucesso retorna comprimento positivo de no máximo 15.

Falha retorna valor negativo.

O fuzz test exige:

[
1 le len le 15
]

para todo decode bem-sucedido e confirma:

    insn.len == return_value

Bytes inválidos ou unsupported resultam em comportamento `#UD` no interpreter.

## Famílias de operações implementadas

A arquitetura decoder/executor possui classes explícitas para:

- integer ALU;
- MOV;
- MOVZX/MOVSX;
- LEA;
- XCHG;
- PUSH/POP;
- PUSHF/POPF;
- JMP/Jcc;
- CALL/RET;
- shifts/rotates;
- unary integer operations;
- multiply/divide;
- IN/OUT;
- INT;
- IRETQ;
- HLT;
- NOP;
- flag control;
- LEAVE;
- CPUID;
- RDMSR/WRMSR;
- MOV para/de control registers;
- descriptor-table operations;
- SETcc;
- CMOVcc;
- STOS/REP STOS;
- classes explícitas de undefined/unimplemented.

A lista descreve famílias, não todos os opcodes/forms x86.

O decoder source é a autoridade para encodings aceitos.

## Facilities ausentes ou incompletas

A virtual CPU não é uma implementação AMD64 completa.

Áreas relevantes ausentes ou incompletas:

- execução x87 FPU;
- SSE/AVX;
- SYSCALL/SYSRET;
- cobertura completa de system instructions;
- segmentação/privilege transition completa;
- debug registers;
- hardware performance counters;
- APIC/x2APIC completo;
- SMP;
- timing arquitetural completo.

CPUID precisa continuar conservador.

## CPUID determinístico

O CPUID do host nunca é repassado.

Vendor string:

    ChrisCPU    

Leaf 0 anuncia leaf standard máxima 1.

Leaf 1 anuncia apenas features selecionadas implementadas, incluindo bits de TSC, MSR, CMOV, APIC e PSE conforme o source atual.

FPU e SSE não são anunciados.

Leaf extendida `0x80000001` anuncia long mode.

SYSCALL não é anunciado porque a execução ainda não existe, mesmo com EFER armazenando state relacionado.

Isso impede que CPU host diferente altere capabilities visíveis ao guest.

## RFLAGS e ALU

Arithmetic flags são calculados por helpers do ChrisCPU, não herdados do host.

Os tests validam carry, zero, sign, overflow, parity e auxiliary carry em casos representativos.

O resultado correto é o estado visível ao guest, não o flags register do host.

## Modelo de virtual memory

ChrisCPU implementa page walk x86-64 de quatro níveis.

Endereços virtuais precisam ser canônicos segundo a regra de 48 bits.

São tratados:

- PML4;
- PDPT;
- PD;
- PT;
- páginas de 1 GiB;
- páginas de 2 MiB;
- páginas de 4 KiB.

A implementação verifica present, writable e user.

NX é aplicado apenas quando EFER.NXE está habilitado.

Accessed e dirty bits são escritos quando apropriado.

## Semântica de page fault

Falhas de tradução geram bits de erro x86 para:

- present/protection;
- write;
- user;
- instruction fetch.

CR2 recebe o endereço virtual com fault antes do delivery.

Endereço não canônico gera `#GP`.

Falha ao ler page table ou ao resolver target físico pode terminar como `CHRIS_EXIT_UNMAPPED`, em vez de page fault guest.

## Estado do TLB

A interface de backend possui `invalidate_tlb`.

No ChrisCPU isso incrementa um generation counter.

O interpreter atual não mantém translation cache equivalente a TLB físico.

Os page walks são diretos.

Assim TLB invalidation é seam arquitetural, não cache de performance significativo nesta revisão.

## Delivery de exceptions

`chris_raise` registra vector/error e tenta delivery ao guest.

Se IDTR é zero, o evento é reportado ao monitor como:

    CHRIS_EXIT_EXCEPTION

Com IDT existente, ChrisCPU valida o gate e transfere controle.

São aceitos interrupt/trap gates e o campo IST precisa ser zero.

Se delivery normal falha, é tentado double fault.

Se o delivery do double fault também falha, a machine termina em:

    CHRIS_EXIT_TRIPLE

e descarrega recent instruction trace.

## Modelo atual de exception frame

O delivery atual empilha:

    SS
    old RSP
    RFLAGS
    CS
    RIP
    optional error code

antes do handler.

Esse é o contrato atual do ChrisCPU.

Não significa que todas as variantes reais de frame e privilege transitions estejam implementadas.

## Injeção de interrupts

Um backend recebe um pending interrupt vector.

ChrisCPU entrega somente quando:

- a CPU não está parada por outro exit;
- existe IRQ pendente;
- RFLAGS.IF está setado;
- o delay pós-STI terminou.

Não há interrupt controller completo gerando múltiplos vectors em fila.

## Exit reasons

Os motivos públicos são:

    CHRIS_EXIT_NONE
    CHRIS_EXIT_HLT
    CHRIS_EXIT_SHUTDOWN
    CHRIS_EXIT_EXCEPTION
    CHRIS_EXIT_TRIPLE
    CHRIS_EXIT_BREAK
    CHRIS_EXIT_STEP_LIMIT
    CHRIS_EXIT_UNMAPPED

São outcomes do monitor/backend.

Não são process exit codes do guest.

## Step limit

`chris_run` recebe budget máximo de steps.

Se o CPU continua executável quando o budget termina:

    CHRIS_EXIT_STEP_LIMIT

O frontend usa um milhão de steps por default.

Isso fornece término determinístico para loops infinitos em tests.

## Breakpoint

O breakpoint compara RIP antes do fetch.

Ao encontrar o endereço:

    CHRIS_EXIT_BREAK

O debugger interativo também permite novo breakpoint, single step e continue.

É breakpoint de monitor, não modelo de DR0-DR7.

## Trace ring

Toda instrução decodificada entra em ring contendo:

- RIP;
- até 15 raw bytes;
- texto formatado.

O ring possui 256 entradas.

Ele existe mesmo sem full textual trace e pode ser descarregado em falha grave de delivery.

## Barramento de port I/O

A machine suporta oito ranges registrados.

Cada range fornece callbacks IN e OUT.

Tamanhos válidos:

    1 byte
    2 bytes
    4 bytes

Read em porta não mapeada retorna todos os bits em 1.

Write em porta não mapeada é ignorado e retorna sucesso.

Esse é o convention atual da plataforma.

## Serial

ChrisVM mapeia serial 16550-like em:

    0x3f8 .. 0x3ff

Há suporte aos comportamentos usados pelos guests atuais, incluindo:

- divisor latch;
- line/modem control;
- scratch;
- transmit;
- internal loopback.

Bytes transmitidos ficam em buffer host de 8192 bytes e podem ser enviados a um hook.

Não é UART timing-accurate.

## Shutdown port

ChrisVM mapeia:

    0x501

Write cujo low byte seja `1` marca shutdown e termina CPU com:

    CHRIS_EXIT_SHUTDOWN

É ABI específica do ChrisVM, não mecanismo ACPI padrão.

## Dispatch de physical memory

A resolução ocorre na ordem:

1. guest RAM;
2. framebuffer fixo;
3. MMIO registrado.

A ordem importa caso uma revisão futura permita overlap.

A topologia atual evita overlap normal RAM/framebuffer.

## MMIO

A machine suporta oito mappings.

Cada uma contém:

- base;
- length;
- read callback;
- write callback;
- context.

O generic physical access atual quebra transfers MMIO em callbacks de um byte.

Uma operação multi-byte do CPU vira sequência de operações de 1 byte.

Devices que exijam transação atômica mais larga precisam de contrato de bus mais forte.

## Physical address não mapeado

Se um endereço traduzido não é RAM, framebuffer nem MMIO, o physical operation falha.

ChrisCPU converte isso em:

    CHRIS_EXIT_UNMAPPED

em caminhos normais.

Assim "page table mapeou" é distinto de "existe um target físico".

## Framebuffer

O contrato fixo é:

    physical base: 0x02000000
    width:         640
    height:        480
    pitch:         2560 bytes
    pixel storage: 32 bits por pixel

O guest de teste usa valores no estilo XRGB8888.

Qualquer write marca o framebuffer como dirty.

O host pode consultar pixels e exportar a imagem inteira.

## Exportação do framebuffer

O frontend exporta:

- PNG se o path termina em `.png`;
- PPM caso contrário.

Se SDL2 está disponível e o run não é headless, o framebuffer final pode ser exibido em janela software-rendered.

O viewer é conveniência do host, não GPU virtual.

## Modelo de guest ELF

O frontend normal recebe um ELF64 x86-64.

Loader e boot protocol são especificados separadamente em `chrisvm-boot-spec`.

Não existe firmware emulado para descobrir o ELF.

O host o carrega diretamente antes da execução.

## Status de sucesso do frontend

O command-line frontend retorna sucesso somente quando a machine termina em:

    CHRIS_EXIT_HLT

ou:

    CHRIS_EXIT_SHUTDOWN

e qualquer framebuffer dump solicitado funciona.

Exception, triple fault, step limit ou unmapped access não são sucesso.

## Evidência de testes

`make -C chrisvm test` compila e executa:

- suite ChrisVM;
- guest ELF de arithmetic/serial;
- guest ELF de framebuffer splash.

A suite cobre, entre outros:

- integer flags;
- arithmetic;
- memory load/store;
- CALL/RET;
- serial loopback;
- unmapped I/O;
- shutdown port;
- #UD, #PF, #GP e divide error;
- step limit;
- CPUID;
- MSR;
- rejeição de ELF malformado;
- recusa do ChrisHV;
- 2000 iterações determinísticas de decode fuzz;
- MMIO real;
- multiply/divide;
- framebuffer stores;
- serial output.

É evidência forte para o subset atual, não prova de conformidade x86 completa.

## Fronteira de determinismo

ChrisCPU não repassa host CPUID e usa step budget explícito.

O TSC virtual cresce deterministicamente por instrução.

Isso reduz dependência do host.

Porém o campo `deterministic` ainda não é record/replay completo.

Não existe event log geral para replay de devices assíncronos, timers, SMP races ou network input.

## Fronteira de segurança

ChrisVM é um emulator de desenvolvimento.

Guest addresses são mediadas por estruturas de memória do emulator, não tratadas diretamente como host pointers.

Esse desenho é correto para isolamento.

Ainda assim ChrisVM não deve ser tratado como sandbox hardened para código hostil.

Bugs de parser, decoder ou device model podem comprometer o processo host.

## Omissões atuais da plataforma

A machine ainda não emula todo o conjunto necessário para boot do kernel ChrisOS real.

Faltam componentes importantes:

- BIOS/UEFI/Limine;
- PCI config/device topology suficiente;
- AHCI/NVMe/VirtIO block;
- plataforma PS/2/xHCI;
- APIC/IOAPIC/timers suficientes;
- SMP;
- ACPI;
- network/audio nativos;
- backend hardware-assisted funcional.

Por isso ChrisVM ainda não substitui QEMU como plataforma geral do ChrisOS.

## Declaração de conformidade

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, uma implementação conforme do ChrisVM é uma virtual machine determinística single-vCPU de subset x86-64 com:

- shared architecture state;
- execução ChrisCPU;
- four-level paging;
- exception delivery;
- port I/O;
- MMIO;
- serial;
- framebuffer fixo;
- direct ELF boot;
- monitor com break/trace/step limits.

Qualquer capability adicional precisa ser demonstrada no source e tests da revisão antes de ser tratada como parte da especificação.

## Nota de revisão

Esta especificação foi reconciliada contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Mudanças futuras em instruction coverage, boot protocol, memory map, device addresses, backend availability ou exit semantics precisam atualizar explicitamente a especificação ou preservar compatibilidade para callers dependentes desta revisão.
