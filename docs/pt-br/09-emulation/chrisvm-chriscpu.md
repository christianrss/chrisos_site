---
id: chrisvm-chriscpu
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/common/cpuid.c
  - docs/chrisvm/architecture.md
  - docs/chrisvm/machine-model.md
  - docs/chrisvm-boot-protocol.md
symbols:
  - chris_machine_create
  - chris_cpuid
depends_on:
  - emulator-theory
  - x86-64-memory-privilege
related:
  - virtualization-chrishv
---

# ChrisVM e ChrisCPU

## Arquitetura

ChrisVM é a plataforma/máquina virtual. ChrisCPU é o backend interpretador x86-64.

<figure class="figure">
<img src="../../assets/diagrams/chrisvm.svg" alt="Arquitetura ChrisVM">
<figcaption>A máquina possui memória e dispositivos; backends de CPU executam estado arquitetural contra essa máquina.</figcaption>
</figure>

A separação permite que futuro ChrisHV veja a mesma plataforma sem exigir que o guest descubra como a CPU está sendo executada.

## `ChrisMachine`

Machine possui configuração, RAM, registros de I/O/MMIO, serial, framebuffer e instância do backend.

Lifecycle: create → load ELF → instalar boot state → run → destroy.

## Estado arquitetural

`ChrisArchitectureState` é contrato comum. ChrisCPU manipula diretamente; VMX/SVM futuramente mapeará campos equivalentes para VMCS/VMCB.

## Pipeline

Interpreter segue fetch/decode/resolve/execute/flags/exception/interrupt/commit RIP. Instrução que escreve RIP marca `rip_dirty` para evitar incremento genérico adicional.

## CPUID

ChrisCPU expõe CPUID determinístico com vendor `ChrisCPU    ` e apenas features implementadas. Anunciar feature sem implementar faz guest selecionar caminho incompatível.

## Boot protocol v1

v1 inicia guest já em long mode, com page tables, GDT, stack, serial, shutdown e framebuffer linear. Não emula BIOS/UEFI/Limine nesse marco.

O kernel higher-half real é recusado em vez de existir atalho em `kstart`. Isso preserva honestidade arquitetural.

## Evidência atual

Guests independentes já executam aritmética, branches, CALL/RET, memória, serial e HLT; outro desenha splash no framebuffer. Testes cobrem exceptions, ELF inválido, I/O desconhecido, MMIO e pixels.

## Ausências

PCI/VirtIO maduros, timer/APIC/IOAPIC/SMP e ChrisHV funcional ainda não fazem parte da máquina atual. São camadas necessárias antes de substituir QEMU para o kernel completo.
