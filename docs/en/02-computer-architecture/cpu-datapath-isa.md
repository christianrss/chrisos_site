---
id: cpu-datapath-isa
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - logic-sequential
related:
  - x86-64-memory-privilege
  - emulator-theory
---

# CPU datapath and instruction-set architecture

## Processor as an architectural machine

A CPU is not defined merely by the presence of an ALU. At the software boundary it is a state machine governed by an instruction-set architecture (ISA). The ISA specifies encodings and the visible consequences of executing them: register updates, memory accesses, control flow, exceptions and privilege effects.

A minimal architectural state contains a program counter, general registers, status flags and some means of addressing memory. x86-64 additionally exposes segment state, control registers, descriptor tables, model-specific registers and a large exception architecture.

## Datapath

The datapath moves and transforms values. Its conceptual components include:

- register storage;
- arithmetic and logic unit;
- shifters and address-generation logic;
- instruction pointer update logic;
- paths to instruction and data memory;
- multiplexers selecting sources and destinations.

A simple register-register addition illustrates the contract:

```text
instruction decoder
      │
      ├── selects source register A
      ├── selects source register B
      └── selects ADD operation
                    │
                    ▼
                 ALU add
                    │
                    ├── result
                    └── flags
                    │
                    ▼
             destination register
```

The ISA may define carry, zero, sign and overflow flags even though the physical circuit that computes them is not visible.

## Instruction encoding

Machine code is a byte representation of operations and operands. Assembly language gives symbolic names to those encodings. The assembler therefore does not create semantics; it translates a human-readable representation into the ISA-defined binary form.

Variable-length x86 instructions can contain prefixes, opcode bytes, ModR/M, SIB, displacement and immediate fields. Decode is correspondingly more complex than for many fixed-width RISC encodings.

## Fetch, decode and execution

A pedagogical cycle is fetch → decode → execute. Real cores pipeline and overlap these stages, but the architectural result must be consistent with the ordering rules defined by the ISA.

Branches change the next instruction address. Calls additionally preserve a return point according to the software convention and instruction semantics. Loads and stores interact with the memory hierarchy and can fault before producing an architectural result.

## ISA versus ABI

The ISA defines processor behavior. An **application binary interface (ABI)** defines conventions used by software built on top of the ISA: argument registers, caller/callee-saved registers, stack alignment, object formats and symbol rules.

Two operating systems can use the same x86-64 ISA with different syscall ABIs. A compiler must satisfy both the ISA encoding rules and the ABI expected by its environment.

## Privileged architecture

Operating systems need mechanisms unavailable to ordinary applications. x86-64 supplies privilege levels and privileged instructions for operations such as changing page-table roots, installing descriptor tables, controlling interrupt state and configuring machine facilities.

The kernel's authority is therefore not a convention enforced by C. It is rooted in CPU privilege checks performed while executing machine instructions.

## ChrisOS and architectural contracts

ChrisOS targets x86-64 for its principal kernel. `kernel/metal` contains code that uses the architecture directly: page-table roots, GDT/IDT installation, interrupt routing and context transitions.

ChrisVM approaches the same architecture from the opposite side. `chrisvm/chris_arch.h` defines architectural state that ChrisCPU must emulate. `chrisvm/cpu/emulator/execute.c` interprets decoded operations and updates that state.

This relationship makes the project useful for documentation:

```text
kernel view                         emulator view
-----------                         -------------
"execute MOV"       <contract>      implement MOV semantics
"load CR3"          <contract>      update CR3 + translation behavior
"receive #PF"       <contract>      detect fault + deliver exception
"write I/O port"    <contract>      dispatch port operation to bus
```

The same ISA is a consumer-facing contract for the operating system and a producer-facing contract for the emulator.
