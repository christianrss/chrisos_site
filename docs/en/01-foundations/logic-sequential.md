---
id: logic-sequential
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - transistor-cmos
related:
  - cpu-datapath-isa
---

# Logic, state and sequential circuits

## Combinational logic

A combinational circuit has no intentional memory: its output is a function of its present input. Decoders, multiplexers, comparators, encoders and arithmetic units are built from this class of logic.

A one-bit full adder accepts `A`, `B` and carry-in `Cin` and produces sum `S` and carry-out `Cout`:

```text
S    = A XOR B XOR Cin
Cout = (A AND B) OR (Cin AND (A XOR B))
```

Repeating and optimizing this primitive yields wide integer addition. Subtraction can be expressed through two's-complement arithmetic, allowing shared adder hardware.

## Multiplexers and controlled dataflow

A multiplexer chooses one of several values according to control bits. This simple operation is pervasive in CPUs: it chooses ALU operands, next program counters, register writeback values and exception vectors.

A datapath can therefore be understood as data storage plus combinational transformation plus multiplexed routing.

## Feedback and stored state

If a circuit's output influences its future input, the circuit can retain information. Cross-coupled gates create bistability: two stable configurations encode one bit.

A latch is level-sensitive. A flip-flop is normally modeled as capturing input on a clock edge. Actual implementations vary, but the architectural purpose is identical: isolate a state transition at a defined synchronization event.

Grouping storage elements creates a **register**. A 64-bit architectural register conceptually stores 64 binary state elements, although high-performance CPUs may rename, replicate or transform physical storage internally.

## Clocked synchronous systems

In a synchronous design, state changes at controlled clock events while combinational logic computes between events.

```text
registers ──> combinational logic ──> registers
    ▲                                  │
    └──────────── clock ───────────────┘
```

The longest relevant combinational path constrains maximum clock frequency together with setup time, clock uncertainty and other margins.

The clock does not make computation intrinsically discrete. It provides an engineering discipline for coordinating analog circuits whose propagation takes finite time.

## Finite-state machines

A finite-state machine combines stored state with next-state logic:

```text
next_state = F(current_state, input)
output     = G(current_state, input)
```

Control units, bus protocols and device controllers can be reasoned about as state machines. The same concept appears in software drivers: a driver often mirrors hardware states such as reset, negotiated, ready, active and failed.

## Memory arrays

Registers are efficient for small, frequently accessed state. Larger storage uses denser cell structures organized into arrays. SRAM is commonly associated with caches; DRAM uses a denser capacitive cell and requires refresh.

Software sees addresses and bytes rather than individual cells. Memory controllers, caches, coherence systems and MMUs stand between a CPU instruction and physical memory devices.

## From state machine to instruction processor

A processor must repeatedly perform a conceptual cycle:

```text
fetch instruction
      ↓
decode operation
      ↓
read required state
      ↓
execute transformation
      ↓
access memory if required
      ↓
write architectural result
      ↓
select next instruction address
```

A simple CPU may map this sequence directly to hardware states. A modern out-of-order core internally overlaps and reorders work while preserving the architectural behavior required by the ISA.

This distinction is fundamental to emulation. ChrisCPU need not reproduce a commercial processor's pipelines, branch predictors, caches or transistor timing. It must reproduce enough of the **architectural contract** that guest software observes correct registers, memory, flags and exceptions.

## Architectural versus microarchitectural state

Architectural state is visible to software according to the ISA: general-purpose registers, RIP, RFLAGS, control registers, selected MSRs and memory.

Microarchitectural state is implementation-specific: reorder buffers, decoded micro-op caches, predictor tables, physical register files and internal queues.

An operating system is written against architectural state. Performance depends heavily on microarchitecture, but functional correctness must not rely on hidden implementation details unless a platform specification explicitly exposes them.

The next volume formalizes the CPU, instruction-set architecture and x86-64 execution environment.
