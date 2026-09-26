---
id: logic-sequential
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/cpu/emulator/chriscpu.c
- chrisvm/cpu/common/state.c
symbols:
- cpu_run
- maybe_irq
- chris_arch_reset
depends_on:
- transistor-cmos
- combinational-logic
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

## A complete transition contract

The equations for F and G become useful only after defining the observation event. Consider a teaching controller with a request input, a completion input and an error input, all sampled on one rising clock edge. It accepts at most one operation, issues a one-cycle start indication and holds a completion indication until the requester releases its request. This example is a specified abstract controller, not a claim that ChrisOS contains this exact circuit.

Use four states: IDLE, ISSUE, WAIT and DONE. Reset selects IDLE and clears the captured error result. ISSUE unconditionally advances to WAIT. In WAIT, error has priority over completion; either ends the operation and enters DONE. DONE remains until request is low. The error result is stored when leaving WAIT, because a transient error input must remain reportable after the input disappears.

| Present state | Sampled condition | Next state | State-derived output |
|---|---|---|---|
| IDLE | Request absent | IDLE | Ready |
| IDLE | Request present | ISSUE | Ready before transition |
| ISSUE | Any | WAIT | Start |
| WAIT | Neither error nor completion | WAIT | Busy |
| WAIT | Error | DONE, store failure | Busy before transition |
| WAIT | Completion without error | DONE, store success | Busy before transition |
| DONE | Request still present | DONE | Completion held |
| DONE | Request absent | IDLE | Completion before transition |

The table makes an important limitation visible: a completion pulse during ISSUE is ignored. The environment must promise that completion remains available in WAIT, or the controller must be redesigned to sample completion in ISSUE as well. Hiding this case behind an arrow labeled “execute” would conceal a protocol gap. A state machine is correct only relative to its input assumptions.

![Controller transitions and retained completion](../../assets/diagrams/sequential-controller.svg)

## Moore and Mealy outputs

In the example, start depends only on being in ISSUE and completion depends only on being in DONE. These are Moore-style outputs. A Mealy-style start could instead depend on IDLE AND request, allowing a response within the current combinational interval. That reduces a cycle of interface latency but introduces an input-to-output path. Chaining such paths across modules can create a long timing path or a combinational loop if ready and valid signals depend on each other without storage.

Moore does not mean glitch-free by definition. Multiple encoded state bits may change with different delays, and combinational decoding of them can transiently produce an unintended output. A registered output has a different timing contract from an arbitrary combinational decode of a register. Mealy does not mean incorrect: it requires a precise account of input stability, propagation and sampling. The useful distinction is where current inputs enter the output function.

The start indication lasts one state interval, not an infinitesimal instant. A receiver using the same clock can sample it under the specified timing contract. A receiver using another clock needs a crossing protocol. A state diagram cannot silently turn a one-cycle pulse into a reliably observed asynchronous event.

## Encoding, reachability and recovery

Four states require at least two encoding bits. Binary encoding minimizes that count, while one-hot encoding uses one bit per state and can simplify some decoding. One-hot is not inherently safer: zero-hot and multiple-hot patterns are invalid and require a policy. Binary encodings can also have unused combinations when the state count is not a power of two. Recovery might select reset, latch an error or stop accepting work, depending on the consequences of losing transaction state.

Reachability starts from the reset state and follows all permitted transitions. An unreachable encoding can be treated as a synthesis don't-care only under the relevant design assumptions; it cannot be declared impossible merely because normal software never requests it. Fault injection, incomplete reset and asynchronous inputs can invalidate those assumptions. A secure controller must consider whether an illegal state might accidentally enable a privileged action.

Two invariants of the teaching controller are that at most one start interval occurs before DONE and that completion remains asserted until request is released. A progress property is that an accepted request eventually reaches DONE if the environment eventually supplies completion or error. The condition on the environment is indispensable: the transition table alone cannot guarantee progress from WAIT. Safety says a prohibited event never occurs; liveness says a required event eventually occurs under stated assumptions.

## Old state and next state must remain separate

A synchronous transition evaluates F from the old state and sampled inputs, then commits the resulting state. In a software model, sequential assignments can accidentally use newly written values where old values were intended. For example, a simultaneous exchange requires `next_a = old_b` and `next_b = old_a`; executing `a = b; b = a` loses the original a. Temporary next-state storage or a carefully ordered equivalent is part of the model's correctness.

The same problem appears in counters with terminal conditions. Testing a count before incrementing can emit a pulse on a different event from incrementing before testing. Both are valid algorithms if the contract specifies them, but they are not interchangeable. A diagram should label whether a condition refers to current count, computed next count or an independently sampled input.

Software simulation also needs to define the granularity of a transition. One emulator step can represent an entire architectural instruction while a hardware design uses many internal cycles. Equivalence should compare the chosen observation boundaries, not require every intermediate host variable to correspond to a physical flip-flop. Conversely, an instruction-level abstraction must still preserve architecturally visible exception and memory effects.

## The actual ChrisCPU loop boundary

`cpu_run` supplies a concrete example of explicit state progression. Before execution it clears `rip_dirty`. After `chris_execute`, it increments RIP by decoded instruction length only when `rip_dirty` is false and the CPU is not halted. An instruction that explicitly redirects control must therefore communicate that fact to the loop. Without the guard, a taken branch target could receive an erroneous additional instruction-length increment.

The loop checks breakpoints before fetching. Fetch failure and decode failure can leave the loop before execution. After the execution path, it considers interrupt delivery and increments software counters. These positions matter: they define which observations share a step boundary and which failures leave before that boundary. The implementation is not a single atomic assignment of a complete next-state object. Its correctness depends on the ordering and contracts of its called routines.

The helper `maybe_irq` first consumes `sti_delay` and returns when it is set. Otherwise it rejects delivery when halted, when no interrupt is pending, or when the interrupt-enable flag is clear. Only after those conditions does it clear the pending marker and call `chris_raise`. This is a control predicate over stored state. It is not evidence of a modeled interrupt wire, analog synchronizer or physical interrupt-controller timing.

## Initialization, concurrency and evidence

The controller example also separates result validity from result value. A stored success bit in IDLE does not mean an operation has just completed; only the DONE state makes that bit meaningful to the receiver. This pattern prevents stale data from being interpreted as a new event. Clearing every payload byte is unnecessary if validity is correctly enforced, but leaving validity asserted during reset can expose old results. In operating-system interfaces the analogous obligation is to distinguish an allocated object, an initialized object and a published object, even when all three occupy the same address.

`chris_arch_reset` clears the architectural structure and sets its explicit initial flags and CR0 bits. Backend reset has additional responsibilities outside that structure. A state diagram for the whole emulator must include device state, pending events and ownership of memory, rather than equating architectural reset with construction of every object. Likewise, the sequential order of one host thread does not grant safe concurrent access from arbitrary other threads.

For a circuit, verification would compare transitions, reset and output timing against the specified input assumptions. For the source discussed here, the evidence is inspection of `cpu_run`, `maybe_irq` and `chris_arch_reset` at the recorded revision. No formal proof of the complete emulator is asserted. A meaningful integration test must distinguish straight-line RIP advancement, explicit control transfer, fetch/decode failure and interrupt deferral; treating all of them as an undifferentiated “CPU ran” outcome would miss the state contract.
