---
id: chrisvm-chriscpu
lang: en
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
symbols:
  - chris_machine_create
  - chris_cpuid
depends_on:
  - emulator-theory
  - x86-64-memory-privilege
related:
  - virtualization-chrishv
---

# ChrisVM and ChrisCPU

## Architecture

ChrisVM is the virtual machine/platform. ChrisCPU is the software x86-64 interpreter backend.

<figure class="figure">
<img src="../../../assets/diagrams/chrisvm.svg" alt="ChrisVM architecture">
<figcaption>The machine owns memory and devices; CPU backends execute architectural state against that machine.</figcaption>
</figure>

This separation is essential because a future ChrisHV backend should see the same virtual platform rather than requiring the guest to detect how its CPU is being executed.

## `ChrisMachine`

The machine owns configuration, RAM, I/O/MMIO registrations, serial, framebuffer and a CPU backend instance.

Lifecycle documented in source:

1. create machine and backend CPU;
2. load ELF segments;
3. install boot protocol state;
4. run backend;
5. destroy/shutdown.

The CPU backend does not own the virtual platform.

## Architectural state

`ChrisArchitectureState` is the common state contract. ChrisCPU reads/writes it; a future VMX/SVM backend would translate equivalent fields to/from VMCS/VMCB state.

Centralizing state avoids creating one architecture definition for each execution backend.

## ChrisCPU pipeline

The current interpreter follows fetch/decode/resolve/execute/flags/exception/interrupt/commit-RIP stages. An instruction that explicitly changes RIP marks that fact so the generic loop does not also add instruction length.

HLT advances according to the implemented contract and exits the test run.

## CPUID identity

ChrisCPU exposes deterministic CPUID rather than forwarding the host processor wholesale. The vendor string is `ChrisCPU    ` and only implemented features should be advertised.

This is crucial. Advertising an instruction or system facility the emulator does not implement causes guests to choose code paths that later fail.

## Boot protocol v1

Current v1 deliberately starts the guest already in 64-bit long mode with initial page tables, GDT, stack, serial port, shutdown port and a fixed linear framebuffer.

It does not emulate BIOS/UEFI/Limine for this milestone.

The protocol currently refuses the higher-half ChrisOS kernel ELF rather than special-casing `kstart`. This preserves architectural honesty: booting the real kernel is a future protocol/machine milestone, not a hidden shortcut.

## Current execution evidence

Project documentation records independent ELF guests performing arithmetic, branches, calls/returns, memory access, serial output and HLT, plus a framebuffer splash using repeated stores.

Tests cover several exceptions, malformed ELF, unknown I/O, MMIO and framebuffer output.

## What is absent

The current machine specification explicitly excludes mature PCI/VirtIO platform support, timer/APIC/IOAPIC/SMP and functional ChrisHV. Those absences define the next machine-development layers required before ChrisVM can replace QEMU for the full ChrisOS kernel workflow.
