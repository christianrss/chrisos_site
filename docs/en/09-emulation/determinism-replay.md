---
id: determinism-replay
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/config.c
  - chrisvm/machine/machine.c
  - chrisvm/cpu/common/cpuid.c
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/frontend/view.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisConfig
  - ChrisArchitectureState
  - chris_config_init
  - chris_cpuid
  - chris_run
  - chris_trace_push
depends_on:
  - chrisvm-debugger
  - chris-architecture-state
  - chrisvm-devices
related:
  - chrisvm-machine
  - chrisvm-boot
  - emulator-theory
---

# Determinism and replay in ChrisVM

## Scope

Deterministic execution and deterministic replay are related but different properties.

A deterministic virtual machine produces the same architecturally relevant result when it starts from the same complete state and receives the same ordered external inputs.

Deterministic replay goes further: the system records enough nondeterministic inputs and scheduling decisions from one execution to reproduce that execution later.

At the inspected ChrisOS revision, ChrisVM has several deterministic-by-construction components, but it does **not** yet implement a complete record/replay subsystem.

The configuration field:

    cfg.deterministic

exists and defaults to one, but no inspected execution path branches on that field. Therefore it is not currently a functional mode switch.

The correct description of the present implementation is:

    deterministic tendencies in a small synchronous interpreter
    !=
    implemented deterministic/replay architecture

This distinction prevents project intent from being confused with current behavior.

## Why determinism matters for ChrisVM

ChrisVM is intended as a controlled execution environment for operating-system and CPU work.

Determinism is especially valuable for:

- reproducing decoder or execution faults;
- comparing emulator revisions;
- validating exception delivery;
- regression testing;
- debugging guest boot failures;
- preserving evidence for research results;
- eventually comparing ChrisCPU and ChrisHV backends.

Without a determinism contract, a failure that depends on timing, asynchronous input or host state can disappear between runs.

With a strong contract, an execution can be identified by initial state, input stream and implementation revision.

## Required model

A useful deterministic-execution model can be written as:

    S_(n+1) = F(S_n, I_n, V)

where:

- S_n is complete machine state before step n;
- I_n is the ordered external input consumed at that step;
- V is the versioned machine/CPU semantics;
- F is the transition function.

Replay requires enough recorded information to reconstruct every I_n that is not already derivable from S_n and V.

If host time, asynchronous device input, thread scheduling or host CPU features enter F without being captured, replay is incomplete.

## Current configuration surface

ChrisConfig contains:

    int deterministic;

chris_config_init initializes it to:

    1

and the command-line parser accepts:

    --deterministic

which also sets it to one.

There is no corresponding --nondeterministic option.

More importantly, the inspected machine, CPU, bus and device execution paths do not use cfg.deterministic to select alternate behavior.

The field currently expresses intended policy rather than an implemented mode.

## Consequence of defaulting an unused flag to one

A default value of one can easily create a false implication that the VM has already enabled a formal deterministic engine.

It has not.

A configuration switch is meaningful only if it controls observable semantics or validation policy.

Until that happens, callers should not use cfg.deterministic as evidence that a run is replayable.

## Single-threaded interpreter advantage

ChrisCPU executes one virtual CPU in one host control loop.

ChrisMachine owns exactly one ChrisCpu pointer, and cpu_run advances one decoded instruction at a time.

There is no guest SMP scheduler inside the current ChrisVM machine and no concurrent device thread modifying guest-visible state.

That removes a major source of nondeterminism: inter-vCPU scheduling.

For the current machine, instruction order is therefore directly defined by the interpreter control flow, exceptions, branches and injected events.

This property is useful but does not by itself establish full determinism.

## Instruction budget as a deterministic boundary

chris_run receives an explicit max_steps budget.

ChrisCPU maintains:

    cpu->steps

and increments it once per interpreter iteration after execution and IRQ consideration.

If no other stop reason occurs before the budget is consumed, the VM returns:

    CHRIS_EXIT_STEP_LIMIT

This makes instruction count a reproducible execution boundary for synchronous workloads.

A test can therefore state that a guest ran for N interpreter steps rather than relying on host elapsed time.

## Virtual TSC progression

ChrisArchitectureState contains:

    uint64_t tsc

and the interpreter increments it once per completed loop iteration:

    cpu->arch.tsc++;

The value is therefore tied to interpreter progress rather than host wall-clock time.

For identical execution paths, this progression is deterministic.

It should not be interpreted as physical CPU cycles, frequency or real elapsed nanoseconds.

The current model is closer to a logical instruction-time counter.

## TSC exposure gap

The virtual CPUID leaf advertises the x86 TSC feature bit.

However, the inspected ChrisCPU operation model does not define a dedicated RDTSC operation in the public opcode enum, and no ChrisVM RDTSC execution path was found in the reviewed sources.

This creates a contract gap:

- architectural state contains tsc;
- CPUID advertises TSC;
- interpreter bookkeeping advances tsc;
- guest instruction-level access is not established by the current reviewed implementation.

A determinism specification should resolve this mismatch before treating virtual TSC as a stable guest ABI.

## Deterministic CPUID

chris_cpuid deliberately does not forward the host processor's CPUID.

Instead, it returns a fixed virtual identity including the vendor string:

    "ChrisCPU    "

and a deliberately constrained feature set.

This is an important deterministic design choice.

If host CPUID were forwarded, the same guest could observe different feature bits on different development machines, making execution environment identity host-dependent.

The current virtual CPUID removes that source of variation.

## CPUID as part of replay provenance

Fixed CPUID output is deterministic for the inspected revision, but replay still needs revision provenance.

If a future commit changes:

- vendor data;
- family/model fields;
- advertised features;
- extended leaves;

the same guest can take a different branch.

Therefore a replay record should identify the ChrisOS/ChrisVM revision or a versioned virtual CPU model, not merely store external events.

## Initial machine state

chris_machine_create uses zero-initialized allocations for the machine and guest RAM.

The framebuffer allocation is also zero-initialized.

The serial state is cleared during attachment.

chris_arch_reset zeros the architectural state and then establishes fixed baseline fields.

For a fresh process and fixed configuration, this provides a largely reproducible starting state.

The boot protocol then writes deterministic page tables, GDT entries and selected initial registers.

## Initial-state completeness

A future replay snapshot cannot include only ChrisArchitectureState.

Complete reproducibility also depends on machine state such as:

- guest RAM contents;
- framebuffer pixels and dirty state;
- serial registers and buffered output;
- shutdown state;
- I/O/MMIO device state;
- pending interrupt state;
- debugger/runtime state when relevant.

CPU registers are necessary but not sufficient.

## Serial output is synchronous

The current UART-like serial device has no host receive stream or timing engine.

Ordinary guest transmit writes synchronously:

- update the fixed TX buffer when capacity remains;
- invoke the optional host hook.

There is no simulated baud delay or asynchronous receive thread.

This behavior is deterministic from the guest's current execution sequence, although the host callback itself can have arbitrary external side effects.

Those host-side side effects are outside guest architectural state.

## Serial callback boundary

The serial hook stores a raw host function pointer and context.

Such pointers must never be serialized as replay state.

A replay system should record guest-visible device events, not process-local callback addresses.

On replay, the frontend can reconnect a new output sink without changing the recorded virtual hardware state.

## Framebuffer behavior

Guest framebuffer writes synchronously modify host-allocated backing memory and set a dirty flag.

The framebuffer itself has no scanout clock, asynchronous refresh, vblank interrupt or timing model.

Thus identical guest stores produce identical backing pixels.

The SDL viewer is host presentation after or around guest execution and should remain outside the deterministic guest state contract.

## SDL host time is not VM time

chris_view_show uses SDL_GetTicks and SDL_PollEvent while presenting a framebuffer snapshot.

Those calls depend on host wall time and user window events.

They do not currently drive CPU execution or guest-visible device timing.

Therefore they are nondeterministic host UI behavior but are not part of the current guest execution transition function.

A future interactive input device would change that boundary and would require event recording.

## MMIO and port I/O

Current I/O and MMIO callbacks execute synchronously in the interpreter thread.

This helps reproducibility because device effects occur in direct program order.

However, generic callbacks can point to host-defined contexts.

ChrisVM cannot claim deterministic behavior for arbitrary externally supplied callbacks unless their inputs and effects obey the same deterministic contract.

The built-in machine is more constrained than the generic callback API.

## Interrupt injection

The backend interface provides:

    inject_irq(cpu, vector)

ChrisCPU records one pending vector through irq_pending/irq_vector.

The run loop checks pending IRQ state at a deterministic point after instruction execution.

For a fixed injection point, behavior is reproducible.

What is not yet defined is how an asynchronous host producer would choose that injection point.

A replay architecture must record an event coordinate such as:

    inject vector V before/after logical step N

rather than relying on host thread timing.

## STI delay and event ordering

ChrisCPU models a one-iteration STI delay through cpu->sti_delay.

The IRQ check occurs after execution and before the step/TSC counters advance.

These ordering details are part of deterministic semantics.

A replay record that uses step numbers must define whether events are injected:

- before fetch;
- before execute;
- after execute;
- before interrupt arbitration;
- after step increment.

Ambiguous event coordinates produce off-by-one replay divergence.

## Host wall clock

No host wall-clock query was found in the core ChrisVM CPU run loop, machine creation path, serial device or framebuffer device.

This is favorable for deterministic interpretation.

Host-time calls do exist in presentation/test tooling elsewhere in the repository, but that does not make them guest time.

The boundary must remain explicit as the VM gains devices.

## Randomness

No random-number source was found in the reviewed ChrisVM core path.

There is no modeled RDRAND/RDSEED facility and no host RNG injection in the current built-in devices.

If randomness is later introduced, replay requires either:

- deterministic seeded generation with the seed recorded;
- or recording the exact random values consumed.

Forwarding host randomness without recording would break replay.

## File and image loading

The guest ELF is an external input.

For reproducibility, a replay record should identify the exact image bytes, preferably by cryptographic hash.

A path name is insufficient because the file at that path can change.

The same rule applies to future disk images, firmware blobs or network capture files.

## Current tests

test_chrisvm.c exercises many deterministic-style workloads:

- fixed byte sequences;
- arithmetic;
- exceptions;
- serial loopback;
- shutdown;
- CPUID/MSR behavior;
- MMIO;
- framebuffer stores;
- splash rendering;
- decoder fuzz input generated from a fixed arithmetic sequence.

These tests are useful regression evidence because their inputs are controlled.

They do not constitute a replay test because no run log is recorded and consumed by a second execution.

## What replay would need to record

A minimal future record format should include at least:

- format version;
- ChrisVM virtual-machine model version;
- source/build revision;
- guest image hash;
- initial RAM size and machine configuration;
- initial CPU/device state or a snapshot identifier;
- every external input event;
- event ordering coordinate;
- interrupt injections;
- future keyboard/mouse input;
- future network receive data;
- future storage completion events when timing can vary;
- any nondeterministic random/time values;
- terminal state digest.

The record must exclude process-local addresses and callbacks.

## State digest

Replay validation should not only run to the same exit reason.

A useful terminal digest can cover deterministic state such as:

- GPRs and control registers;
- RIP/RFLAGS;
- selected MSRs;
- RAM hash;
- device-state hash;
- framebuffer hash when relevant;
- serial output hash;
- step count;
- virtual TSC;
- exit reason and exception metadata.

Comparing these values helps identify the first class of divergence.

## Checkpointing

Long executions benefit from checkpoints.

A checkpoint can contain a complete virtual-machine snapshot plus the event-log offset.

Replay can then resume from checkpoint K instead of executing from the beginning.

Current ChrisVM lacks a complete machine snapshot format, so checkpointed replay is future work.

The existing ChrisArchitectureState is only one component of such a snapshot.

## Reverse debugging

Reverse execution is not implemented.

Deterministic replay can eventually support reverse debugging by restoring an earlier checkpoint and replaying forward to a target step.

This is preferable to trying to invert every machine instruction and device mutation.

The current debugger's step counter and trace ring provide useful building blocks, but they are not sufficient on their own.

## ChrisCPU versus ChrisHV

A future replay contract should sit above the CPU backend where possible.

If ChrisCPU and ChrisHV both consume the same versioned machine state and event stream, deterministic traces could become a differential-testing tool.

However, hardware-assisted execution introduces additional sources of nondeterminism:

- host interrupt timing;
- VM exits;
- hardware timers;
- device virtualization timing;
- host scheduling.

ChrisHV cannot simply inherit ChrisCPU's current deterministic tendencies.

It will need explicit interception and event control.

## SMP implications

The current single-vCPU model avoids scheduling nondeterminism.

Adding SMP changes the problem substantially.

A replayable SMP system must control or record:

- vCPU scheduling order;
- instruction or event quanta;
- interrupt destination and delivery order;
- atomic-memory interleavings;
- device completion visibility;
- memory-order interactions.

Recording only external I/O is not enough if internal vCPU interleaving can vary.

## Memory model and replay

Deterministic replay is stricter than deterministic source code.

With multiple CPUs, two legal executions under the same memory model can observe different interleavings.

The replay layer must reproduce the chosen execution, not merely stay within the set of architecturally legal executions.

For the current one-vCPU interpreter this issue is largely absent.

## Failure semantics

A replay system must make failures reproducible too.

If execution stops with:

- CHRIS_EXIT_EXCEPTION;
- CHRIS_EXIT_TRIPLE;
- CHRIS_EXIT_UNMAPPED;
- CHRIS_EXIT_BREAK;
- CHRIS_EXIT_STEP_LIMIT;

the event log and final state should permit the same stop point to be reconstructed.

The existing recent-instruction ring is valuable supporting evidence but is not a substitute for a complete event log.

## Observability versus determinism

Tracing does not create determinism.

The current instruction trace and recent-instruction ring observe execution after choices have been made.

A replay log records the choices that could not be recomputed from deterministic state.

The two mechanisms should remain separate:

    trace = explain what executed
    replay log = reproduce nondeterministic inputs/decisions

Both can share step coordinates and revision metadata.

## Security and privacy boundary

A future event log can contain guest input and device payloads.

Network packets, keyboard input, disk data or secrets may therefore appear in replay artifacts.

Replay files should be treated as potentially sensitive execution captures.

The current implementation has no replay artifact and therefore no storage/encryption policy yet.

## Performance trade-offs

The present synchronous design has low conceptual overhead.

A full replay engine adds costs for:

- event serialization;
- state hashing;
- snapshot memory;
- checkpoint I/O;
- optional device-data capture.

The cost can be controlled by recording only true nondeterministic inputs and using periodic checkpoints rather than full state after every instruction.

## Required validation for a real deterministic mode

Before cfg.deterministic can be treated as an operational guarantee, automated tests should demonstrate at least:

1. two independent runs from identical inputs produce equal state digests;
2. CPUID output is independent of host CPU;
3. virtual time progression is identical;
4. serial/framebuffer results are identical;
5. injected IRQs at recorded coordinates reproduce the same execution;
6. a recorded event stream can drive a fresh run;
7. mutation or omission of an event is detected as divergence;
8. replay remains stable across supported hosts for the same virtual-machine version;
9. incompatible model/revision changes are rejected or migrated explicitly.

## Implementation priorities

The highest-value next steps are:

1. either make cfg.deterministic operational or remove the misleading switch until it is;
2. define a versioned virtual-machine model identifier;
3. define complete snapshot ownership beyond ChrisArchitectureState;
4. formalize logical event coordinates around interpreter steps;
5. add deterministic state hashing;
6. add a small event-log format;
7. record/replay IRQ injection first as the simplest asynchronous event;
8. hash guest ELF input;
9. preserve deterministic CPUID as an explicit virtual CPU contract;
10. resolve TSC advertisement versus guest instruction support;
11. keep host UI callbacks outside serialized guest state;
12. add replay tests before adding asynchronous input devices;
13. extend the model deliberately for SMP and ChrisHV rather than assuming current behavior scales.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisVM is a single-vCPU synchronous interpreter with several reproducibility-friendly properties: fixed virtual CPUID, zeroed initial allocations, logical step counting, a virtual TSC advanced by interpreter progress, synchronous built-in devices and no core wall-clock/RNG dependency found in the reviewed path. However, cfg.deterministic is not consumed as an execution switch, and there is no event recorder, replay reader, complete snapshot format, checkpoint system or reverse execution. ChrisVM therefore has deterministic foundations, not a completed deterministic replay subsystem.
