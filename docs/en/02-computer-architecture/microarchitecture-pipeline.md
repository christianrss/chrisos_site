---
id: microarchitecture-pipeline
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
symbols:
  - ChrisArchitectureState
  - ChrisInsn
  - ChrisCpu
  - fetch_insn
  - cpu_run
  - chris_decode
  - chris_execute
depends_on:
  - cpu-datapath-isa
  - clock-timing
  - registers-counters
related:
  - pipeline-hazards-forwarding
  - branch-prediction-speculation
  - out-of-order-renaming-retirement
  - cache-hierarchy
---

# CPU microarchitecture and pipelining

## Scope: ISA is the contract; microarchitecture is the implementation

An instruction-set architecture defines the state visible to software and the rules by which instructions transform that state. A microarchitecture is a concrete mechanism that realizes those rules. Two processors can implement the same x86-64 ISA while using very different fetch widths, pipeline depths, execution units, cache hierarchies, branch predictors, rename structures and retirement machinery.

This distinction is essential for ChrisOS because the project touches both sides of the contract. The kernel consumes the x86-64 architectural interface. ChrisCPU, inside ChrisVM, produces an executable model of part of that interface. The current ChrisCPU implementation is an instruction interpreter: it fetches bytes, decodes one instruction, executes its semantics, advances or replaces RIP, handles an interrupt boundary, increments counters and then begins the next iteration. It does not model a clocked hardware pipeline, pipeline registers, per-stage occupancy, forwarding paths, issue width or cycle-accurate resource contention.

That does not make pipeline theory irrelevant. The operating system runs on real pipelined processors, and a future timing-oriented ChrisCPU model would need explicit microarchitectural state. The purpose of this chapter is therefore twofold:

1. explain how pipelining transforms a sequential datapath into an overlapped implementation; and
2. establish exactly where the current ChrisCPU abstraction stops, so timing concepts are not mistaken for implemented behavior.

![Conceptual in-order pipeline and architectural retirement boundary](../../assets/diagrams/microarchitecture-pipeline-en.svg)

## From a long combinational path to staged execution

Consider a simple processor that performs all work for one instruction between two architectural state updates. A conceptual path may include:

1. selecting the instruction address;
2. reading instruction bytes;
3. decoding the opcode and operands;
4. reading register operands;
5. generating an effective address;
6. performing an arithmetic or logical operation;
7. accessing data memory;
8. selecting a result;
9. writing the destination and status flags;
10. selecting the next instruction address.

If this entire path is completed in one clock period, the minimum period must exceed the worst delay of the complete path plus register timing margins:

    Tclock >= Tcomb,max + Tsetup + Tskew

where Tcomb,max is the longest combinational delay between state elements, Tsetup is the destination register setup requirement and Tskew represents clock-distribution margin.

The maximum clock frequency is approximately:

    fmax <= 1 / Tclock

Breaking the path into k stages inserts registers between groups of logic. The idealized period becomes bounded by the slowest stage rather than by the sum of all stage delays:

    Tclock,pipeline >= max(Tstage,1 ... Tstage,k) + Treg-overhead

The qualification "idealized" matters. Stage delays are rarely balanced perfectly, pipeline registers cost time and energy, and additional stages create control and dependency penalties. Pipelining improves potential **throughput** by overlapping instructions; it does not imply that the **latency** of one instruction becomes k times smaller.

## Latency, throughput and occupancy

Three quantities must be kept separate:

| Quantity | Meaning | Example in a five-stage scalar pipeline |
|---|---|---|
| Instruction latency | Time from an instruction entering the first stage until its result is architecturally usable | roughly five stage times for a simple instruction |
| Throughput | Long-run completion rate when the pipeline is full | ideally one instruction per cycle |
| Occupancy | Number of instructions simultaneously resident in pipeline state | up to about five in the simple model |

For n independent instructions crossing k equal-latency stages, an ideal pipeline requires approximately:

    cycles = k + n - 1

The first result appears after k cycles; afterward a result can appear each cycle. An unpipelined machine that needs k stage-equivalent intervals per instruction would require approximately n*k intervals. The throughput advantage approaches k only under ideal conditions and large n.

Real execution departs from this simple formula because of stalls, flushes, variable-latency memory operations, multi-cycle functional units, interrupts, exceptions and resource conflicts.

A common performance identity is:

    execution time = instruction count * CPI * clock period

where CPI is cycles per instruction. A deeper pipeline may reduce clock period but increase CPI through larger branch-misprediction penalties or more frequent imbalance. Clock frequency alone is therefore not a complete performance metric.

## A five-stage teaching model

A classic scalar pipeline divides instruction processing into five conceptual stages:

| Stage | Conventional name | Typical work |
|---|---|---|
| 1 | IF — instruction fetch | choose PC/RIP, obtain instruction bytes |
| 2 | ID — decode/register read | interpret encoding, identify operands, read registers |
| 3 | EX — execute/address generation | ALU operation, branch comparison, effective-address calculation |
| 4 | MEM — memory | load/store data access |
| 5 | WB — writeback | publish a register result |

This model is pedagogical, not a description of modern x86 cores. x86 instructions have variable length and are commonly transformed internally into implementation-specific micro-operations. Modern high-performance processors may contain separate front-end queues, decoders, micro-op caches, rename stages, schedulers, multiple execution clusters, load/store queues and retirement structures.

The five-stage model remains valuable because it exposes the central invariant of a pipeline: each stage operates on a different instruction during the same clock interval, and pipeline registers preserve the information required by later stages.

## Pipeline registers are state, not wires

Without stage registers, an instruction's intermediate values would be overwritten by the next instruction. A conceptual IF/ID register may retain:

- the fetched instruction or decoded boundary information;
- the instruction address;
- prediction metadata;
- fault information associated with fetch.

An ID/EX register may retain:

- decoded operation class;
- operand values or operand identifiers;
- immediate value;
- destination register identifier;
- control bits indicating memory or writeback behavior.

An EX/MEM register may retain:

- ALU result or effective address;
- store data;
- branch result;
- destination metadata;
- pending exception information.

A MEM/WB register may retain:

- loaded data or execution result;
- destination register;
- writeback enable;
- fault/valid state.

These structures are not architecturally visible. Software cannot read an IF/ID pipeline register. They are implementation state used to guarantee that the final architectural transformation is correct.

The valid bit is particularly important. A pipeline slot can hold arbitrary stale electrical or simulated bits while being marked invalid. A bubble is therefore best represented as "no valid instruction in this slot", not necessarily as a physical NOP instruction.

## Flow of instructions through the pipeline

Suppose instructions I1 through I5 are independent and each uses all five stages. An ideal schedule is:

| Cycle | IF | ID | EX | MEM | WB |
|---:|---|---|---|---|---|
| 1 | I1 | — | — | — | — |
| 2 | I2 | I1 | — | — | — |
| 3 | I3 | I2 | I1 | — | — |
| 4 | I4 | I3 | I2 | I1 | — |
| 5 | I5 | I4 | I3 | I2 | I1 |
| 6 | I6 | I5 | I4 | I3 | I2 |

Several instructions are active simultaneously, but each occupies a different stage. This overlap is the source of throughput.

The table also shows why implementation correctness becomes more difficult. The machine now contains partially processed younger instructions behind older instructions. If I2 faults while I3 and I4 have already begun processing, the processor needs a policy that prevents younger speculative or partial work from becoming architecturally visible before the exception is delivered.

## Architectural state and retirement

Architectural state is the state the ISA allows software to observe: general-purpose registers, RIP, RFLAGS, control registers, memory effects and other defined machine state. Microarchitectural state includes pipeline slots, predictor tables, queues and transient results.

A simple in-order pipeline can often update architectural state in program order at writeback. More advanced designs separate **execution** from **retirement**. Instructions may execute out of order, but their visible results are committed in program order through a reorder mechanism. That subject is developed in the out-of-order chapter.

The fundamental rule is:

> Work may be overlapped or speculative internally, but the architectural state must reflect a legal execution of the ISA.

This rule is also the bridge to emulator design. An instruction-level interpreter can update architecture directly because it has no overlapping younger instructions to protect. A cycle-accurate pipeline model cannot safely treat every intermediate execution result as committed state.

## Stalls, bubbles and flushes

A pipeline must sometimes stop normal advancement.

A **stall** prevents one or more stages or pipeline registers from accepting new work for a cycle. Upstream stages may also need to stop to avoid overwriting the blocked instruction.

A **bubble** is an invalid slot intentionally inserted so later stages can continue while no new instruction enters a particular position.

A **flush** invalidates younger work that should no longer complete. Typical causes include:

- a taken branch discovered after sequential instructions have already been fetched;
- a branch misprediction;
- an exception or fault;
- a control transfer that changes the instruction stream;
- reset or machine-level redirection.

These operations are distinct. A load-use dependency may require a one-cycle stall and bubble without flushing the whole pipeline. A branch misprediction usually requires redirecting fetch and invalidating wrong-path instructions.

## Stage balance and critical path

Pipelining is limited by the slowest stage. Suppose nominal stage delays are:

| Stage | Logic delay |
|---|---:|
| IF | 320 ps |
| ID | 250 ps |
| EX | 410 ps |
| MEM | 500 ps |
| WB | 180 ps |

If pipeline-register overhead is 40 ps, the minimum idealized clock period is at least 540 ps because MEM is the critical stage. Splitting a 180 ps stage further does not improve the clock period while the 500 ps stage remains unchanged.

This creates an optimization problem. Designers can:

- repartition logic across boundaries;
- duplicate resources;
- pipeline long functional units internally;
- use caches to reduce common-case memory delay;
- allow variable-latency operations to leave the simple fixed-stage path;
- use queues so one delayed operation does not necessarily freeze the whole machine.

Each technique adds area, energy, verification complexity or new hazards.

## Variable-length x86 instructions and front-end implications

A fixed-width ISA can often identify instruction boundaries directly from aligned words. x86-64 cannot. Instructions can be one to fifteen bytes and include prefixes, opcode bytes, ModR/M, SIB, displacement and immediate fields.

A hardware front end therefore has to solve multiple problems before ordinary execution:

- find instruction boundaries in a byte stream;
- fetch across cache-line or page boundaries;
- handle variable numbers of prefixes;
- identify branch targets;
- feed one or more decoders;
- potentially translate complex instructions into micro-operations;
- preserve faults associated with the original architectural instruction.

ChrisCPU exposes a simpler software form of the same boundary problem. The current <code>fetch_insn</code> function attempts to read up to fifteen bytes from the virtual address at <code>arch.rip</code>. <code>chris_decode</code> then interprets prefixes and fields into a <code>ChrisInsn</code> structure. This is an instruction-level decoder pipeline in the ordinary software sense of processing stages, but it is not a clocked CPU pipeline.

That distinction must remain explicit in the documentation.

## Exceptions and precise architectural state

A processor must deliver faults with a coherent architectural context. For many synchronous exceptions, software expects the reported instruction pointer and visible register state to correspond to a defined point relative to the faulting instruction.

In a pipeline, a younger instruction may already have reached execution logic when an older instruction discovers a fault. Precise exception machinery prevents younger work from committing and arranges delivery as though the machine had reached the faulting instruction in program order.

A teaching in-order design can use stage age and valid bits:

1. record the exception with the oldest affected instruction;
2. stop or invalidate younger instructions;
3. allow older safe instructions to complete if the architecture requires it;
4. redirect to the exception handler;
5. provide the architectural restart address and error information.

Real implementations can be substantially more complex, especially with out-of-order execution.

## Interrupt boundaries

External interrupts differ from synchronous faults because they are not caused by the instruction currently executing. Hardware therefore chooses architecturally permitted interrupt-recognition boundaries.

The current ChrisCPU interpreter exposes a clear software boundary. In <code>cpu_run</code> it:

1. fetches the instruction bytes at the current RIP;
2. decodes them;
3. executes the instruction;
4. advances RIP when execution did not explicitly replace it;
5. calls <code>maybe_irq</code>;
6. increments the step and TSC counters.

This ordering means the interpreter checks pending interrupts between completed instruction iterations, subject to its interrupt-enable and STI-delay logic. That is an interpreter contract, not a model of a physical pipeline stage.

A future pipeline model would need an explicit rule for the point at which an asynchronous interrupt becomes architecturally visible and how younger in-flight instructions are discarded or drained.

## Memory latency and pipeline backpressure

The simple five-stage model assigns one cycle to MEM. Real memory is not constant-latency. A load can hit in a first-level cache, miss into another cache, trigger a page walk, reach DRAM or fault. Stores may enter buffers and become globally visible later.

A scalar pipeline with no nonblocking structures may freeze while a memory request is outstanding. More advanced machines use:

- cache miss status structures;
- load queues and store queues;
- store buffers;
- replay mechanisms;
- multiple outstanding memory requests;
- dependency prediction;
- memory-order checks.

These structures decouple execution from raw memory latency, but they also expand the amount of microarchitectural state that must be flushed, replayed or validated.

ChrisCPU currently calls virtual-memory helpers synchronously from instruction execution. A memory access either completes through the emulator's translation/read/write path or returns an error that participates in exception handling. No simulated cache-miss latency or memory-level parallelism is represented by the instruction loop.

## Pipeline depth is a trade-off, not a goal

Increasing pipeline depth can reduce the amount of logic per stage and potentially shorten the clock period. It also causes costs:

- more pipeline registers and clock power;
- longer branch redirection penalties;
- more state to flush;
- greater bypass-network complexity;
- more verification surface;
- more sensitivity to stage imbalance;
- potentially higher instruction latency.

An optimal depth depends on process technology, target frequency, workload, branch behavior, execution resources and power constraints. There is no universal number of stages that defines a "modern" processor.

## Scalar, superscalar and multi-issue execution

A scalar pipeline accepts at most one instruction into a stage per cycle. A superscalar front end can decode or issue multiple operations per cycle. Width changes the resource problem dramatically.

If a machine can issue W operations per cycle, it needs enough register-file ports, rename bandwidth, scheduler capacity, execution units, cache ports and retirement bandwidth to make that width useful. Peak width is only an upper bound. Dependencies and workload mix often reduce achieved instructions per cycle.

The next chapters separate three mechanisms that are often incorrectly collapsed into the word "pipeline":

- **hazard detection and forwarding**, which preserve correctness when overlapped instructions depend on one another;
- **branch prediction and speculation**, which keep the front end supplied across uncertain control flow;
- **out-of-order execution and register renaming**, which allow independent younger work to proceed while preserving ordered architectural retirement.

## Current ChrisCPU implementation

At revision <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code>, the relevant execution state is represented by <code>ChrisCpu</code> and <code>ChrisArchitectureState</code>.

<code>ChrisArchitectureState</code> contains architectural registers and machine-visible state such as:

- sixteen general-purpose registers;
- RIP and RFLAGS;
- CR0, CR2, CR3, CR4 and CR8;
- segment state;
- GDTR and IDTR;
- EFER and selected MSRs;
- XMM storage;
- current privilege level.

<code>ChrisCpu</code> wraps that architecture with emulator-control state such as:

- step count;
- halt and exit reason;
- pending exception and IRQ information;
- STI delay;
- <code>rip_dirty</code>;
- TLB generation;
- tracing configuration and trace ring.

There are no source fields representing IF/ID, ID/EX, EX/MEM or MEM/WB registers. There is no per-cycle stage-valid vector, reorder buffer or forwarding network in the reviewed files.

The central loop can be summarized as:

    while execution budget remains:
        fetch bytes at architectural RIP
        decode bytes into ChrisInsn
        record trace information
        execute the instruction semantics
        if execution did not redirect RIP:
            RIP += instruction length
        check pending interrupt boundary
        increment step and TSC counters

This is intentionally valuable for functional emulation. Each loop iteration forms a clear architectural transition. It is simpler to validate instruction semantics, exceptions and system behavior without first reproducing a physical core's timing.

## What a future pipelined ChrisCPU mode would require

A timing-oriented mode must not be created by merely adding a "cycle" counter around the current instruction loop. It would need new state with explicit semantics.

At minimum, an in-order teaching pipeline would need:

| Structure | Required information |
|---|---|
| Fetch state | fetch RIP, fetched bytes, fetch fault, validity |
| Decode state | decoded <code>ChrisInsn</code>, source/destination identifiers, immediate, validity |
| Execute state | operand values, ALU/address result, branch outcome, exception state |
| Memory state | effective address, load/store data, memory fault, validity |
| Writeback state | result, destination, architectural commit enable |
| Control | stall, flush, redirect, interrupt/exception priority |

The model would also need a clear division between architectural and speculative state. If <code>ChrisArchitectureState</code> remains the committed state, intermediate stage results should live elsewhere until the selected retirement point.

A deterministic cycle API might look conceptually like:

    chris_pipeline_cycle(cpu):
        retire_or_writeback()
        advance_memory()
        advance_execute()
        advance_decode()
        advance_fetch()
        resolve_flush_and_stall_priority()
        account_cycle()

The actual order in software must be designed so updates use prior-cycle state rather than accidentally reading values already modified for the new cycle. A common simulator technique is double buffering: compute <code>next</code> pipeline state from <code>current</code>, then replace the whole microarchitectural state at the clock edge.

## Invariants for a correct pipeline model

Any future implementation should enforce at least these invariants:

1. **Program-order architectural equivalence.** For code without timing-visible devices, committed architectural results must match the functional interpreter.
2. **No invalid-slot side effects.** A bubble must never update registers, memory or control state.
3. **No younger commit after an older fault.** Wrong-path or younger instructions can compute transient values but cannot become architecturally visible when an older exception redirects execution.
4. **Single ownership of stage state.** Every in-flight instruction instance has one well-defined stage or queue entry.
5. **Stable metadata across stalls.** If a stage is stalled, its instruction identity, exception metadata and operand identifiers cannot change accidentally.
6. **Flush dominates younger work.** Redirected instructions must be invalidated before they can publish results.
7. **Cycle updates are edge-like.** New-stage values derive from a consistent previous-cycle snapshot.

These invariants are more important than reproducing any specific commercial CPU pipeline.

## Complexity and storage cost

For a fixed-width scalar pipeline with k stages, advancing pipeline metadata is O(k) in a straightforward software simulator, or effectively O(1) when k is a compile-time constant. Storage is proportional to the sum of the per-stage records.

Hazard detection can increase work. Comparing D source operands against destination metadata from H older hazard-relevant stages costs O(D*H) comparisons in a simple model. Superscalar width W increases pairwise comparisons and port requirements rapidly; naive dependency comparison across multiple instructions can approach quadratic behavior in W.

Hardware performs many comparisons in parallel, so algorithmic complexity in a software simulator should not be mistaken for hardware latency. It does, however, matter for emulator performance.

## Validation strategy

A pipeline model should be validated against the existing functional interpreter rather than replacing it immediately.

A strong differential strategy would:

1. initialize both backends with identical <code>ChrisArchitectureState</code> and memory;
2. run one architectural instruction to commit in the pipelined model;
3. run one instruction in the functional interpreter;
4. compare committed architectural state and defined memory effects;
5. repeat through branches, faults, interrupts and memory accesses.

Additional directed tests should verify:

- fill and drain behavior;
- stall retention;
- bubble propagation;
- flush of wrong-path work;
- exception priority;
- RIP on faults;
- interrupt recognition;
- identical results after long instruction sequences.

Performance counters for cycles, stalls or bubbles may differ by design; architectural state must not.

## Current limitations

The current ChrisCPU code reviewed for this chapter does **not** provide:

- cycle-accurate pipeline timing;
- explicit pipeline registers;
- simulated functional-unit occupancy;
- forwarding or interlock logic;
- branch-predictor timing;
- reorder/retirement structures;
- cache-latency timing;
- memory-level parallelism;
- a measured correspondence to any specific Intel, AMD or other physical x86 microarchitecture.

Any statement that ChrisCPU currently has those mechanisms would be incorrect.

## Roadmap boundary

A pipelined or timing-aware ChrisCPU can be a valuable educational extension because ChrisOS already provides workloads that exercise privileged state, paging, interrupts, system calls and devices. The appropriate path is additive:

1. retain the current functional backend as a correctness oracle;
2. define a separate microarchitectural state structure;
3. implement a minimal in-order scalar timing model;
4. add hazards and forwarding;
5. add branch prediction only after flush semantics are proven;
6. add caches and variable-latency memory behind explicit interfaces;
7. consider superscalar or out-of-order mechanisms only after differential validation is stable.

ChrisHV is a different path: it uses hardware virtualization rather than simulating a pipeline. Shared architectural state can connect these backends, but their microarchitectural behavior should not be conflated.

## Revision record

This chapter was reconciled against ChrisOS <code>main</code> revision <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code>. Implementation claims are limited to the source files declared in the frontmatter. Pipeline timing, stage structures and performance equations are architectural theory unless explicitly identified as current ChrisCPU behavior.
