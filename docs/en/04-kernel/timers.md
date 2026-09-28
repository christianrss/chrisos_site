---
id: timers
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/pit.c
  - kernel/metal/pit.h
  - kernel/metal/irq.c
  - kernel/metal/proc.c
  - kernel/metal/start.c
symbols:
  - pit_init
  - pit_ticks
  - proc_on_tick
  - proc_slice_due
  - proc_slice_ack
depends_on:
  - pic-apic-ioapic
  - idt-exceptions
related:
  - process-lifecycle
  - interrupts-smp
---

# PIT timing and scheduler tick semantics

## Scope

A timer interrupt converts physical or virtualized time into discrete kernel events. The mechanism can be used for wall-clock accounting, sleep queues, scheduler preemption, timeout detection, animation cadence, network retransmission and profiling, but those uses are logically separate. ChrisOS currently programs the legacy Programmable Interval Timer for a 60 Hz periodic interrupt. The IRQ handler increments a global tick counter and marks a process scheduling slice as due. It does not perform a complete context switch inside the interrupt handler.

This chapter separates PIT hardware programming, interrupt routing, tick arithmetic, scheduler signalling and the limitations of using a fixed 60 Hz legacy timer.

## PIT hardware model

The classic 8253/8254-compatible PIT receives an input clock of approximately 1.193182 MHz. Channel 0 is conventionally connected to IRQ0 on PC-compatible systems. Software programs a divisor; the output transition frequency is approximately:

```text
f_out = 1,193,182 / divisor
```

ChrisOS defines `PIT_INPUT_HZ = 1193182` and computes the divisor using integer division.

The divisor is constrained to 16 bits. A requested frequency that produces divisor zero would be too high for the integer representation; a divisor above `0xffff` is too low for the selected PIT mode. `pit_init` rejects both cases, and also rejects zero frequency before division.

## Accepted frequency range and API contract

The implementation's validation implies a concrete integer input domain. Because the divisor is computed as `floor(1,193,182 / frequency_hz)`, it must satisfy:

```text
1 <= divisor <= 65,535
```

For integer requests, 19 Hz is accepted while 18 Hz produces a divisor above 16 bits. At the high end, a request up to 1,193,182 Hz produces divisor 1; a larger request truncates the quotient to zero and is rejected. These are software acceptance bounds, not a claim that every frequency inside the interval is useful or physically accurate.

The API returns only success/failure. It does not return the chosen divisor or actual realized frequency, so callers cannot recover quantization error through the current interface. The boot path avoids that ambiguity operationally by selecting one known policy value, 60 Hz.

## Programming sequence

`pit_init(frequency_hz)` performs:

1. validate the requested frequency;
2. calculate the divisor;
3. reset the global `ticks` counter;
4. install `pit_irq` as the handler for IRQ0;
5. write control byte `0x36` to port `0x43`;
6. write the divisor low byte and then high byte to channel-0 port `0x40`;
7. unmask IRQ0 in the PIC.

The control byte selects channel 0, low-byte/high-byte access, mode 3 and binary counting. Mode 3 is the square-wave generator mode commonly used for periodic system ticks.

The handler is registered before IRQ0 is unmasked. This ordering ensures that the first delivered timer interrupt has a valid callback.

## Boot frequency

`kstart` calls `pit_init(60)`. If the call returns false, the kernel panics with an invalid-frequency message.

At 60 Hz, the nominal tick period is:

```text
T = 1 / 60 s ≈ 16.6667 ms
```

Because `1193182 / 60` is integer division, the actual programmed divisor is 19,886 rather than a fractional value. The actual frequency is therefore the PIT input divided by 19,886, close to but not mathematically identical to 60.000000 Hz. Any long-term timekeeping derived solely from this tick count would accumulate the corresponding quantization and oscillator error.

ChrisOS currently uses the tick primarily as a system cadence/scheduling signal rather than presenting it as a precision real-time clock.

## Divisor quantization and accumulated error

The PIT cannot represent an arbitrary real-valued frequency. ChrisOS computes an integer divisor with truncating division:

```text
divisor = floor(1,193,182 / requested_hz)
actual_hz = 1,193,182 / divisor
```

For the boot request of 60 Hz:

```text
divisor = 19,886
actual_hz ≈ 60.0011063 Hz
actual_period ≈ 16.666359 ms
```

The difference is small for scheduler cadence, but it illustrates an important timekeeping rule: a periodic interrupt count is not automatically a calibrated wall clock. The accumulated phase error after (N) handled ticks depends on the programmed oscillator/divisor error plus interrupt-service latency and any lost or delayed deliveries. If software later derives seconds from `ticks / 60`, that conversion intentionally uses the nominal policy frequency, not a measured physical clock.

A more precise subsystem would keep an explicit conversion ratio or calibrated clocksource and use the PIT only as a clock-event source. ChrisOS does not currently maintain such a calibration state.

## State ownership and update path

The timer path has a small state machine:

```text
pit_init
  -> validate frequency
  -> reset ticks
  -> register IRQ0 callback
  -> program channel 0
  -> unmask IRQ0

IRQ0
  -> pit_irq
  -> ticks = ticks + 1
  -> proc_on_tick
  -> g_slice = 1
  -> generic IRQ layer sends EOI
```

Only the interrupt path increments `ticks`; ordinary code reads it through `pit_ticks`. Similarly, timer code does not clear `g_slice`: the consumer acknowledges the scheduling request with `proc_slice_ack`. This separation means the timer produces an event while scheduler/process code owns consumption.

There is no queue of pending slices. Repeated timer interrupts while `g_slice` is already 1 collapse into the same boolean state. The current design therefore records “at least one scheduling boundary is due,” not how many quanta elapsed. That is sufficient for the present deferred scheduling contract but would lose accounting information if the kernel later needed one-to-one quantum consumption.

## Interrupt route

PIT channel 0 asserts IRQ0. The PIC has been remapped so IRQ0 appears as vector 32. The IDT common stub creates `irq_frame` and invokes `irq_dispatch`. For vectors 32–47, the dispatcher derives the legacy IRQ number. IRQ0 is then sent to the registered `pit_irq` function.

After the callback returns, `irq_dispatch` sends EOI through `irq_eoi`. The timer handler itself does not directly touch PIC command ports.

This separation makes the PIT driver responsible for time semantics and the generic IRQ layer responsible for controller completion.

## Tick counter

`ticks` is declared `volatile uint64_t` and incremented by the interrupt handler. `pit_ticks()` returns the current value.

`volatile` tells the compiler that asynchronous code may change the object and prevents certain optimizations that would cache it as if normal single-threaded C rules applied. It does not by itself make arbitrary multi-CPU read-modify-write operations atomic or establish a full memory-ordering protocol.

In the reviewed design, IRQ0 is a BSP-oriented legacy interrupt route, and the increment occurs in that interrupt context. If timer delivery were distributed across CPUs later, the ownership/atomicity rules would need to be reconsidered.

A 64-bit counter at 60 Hz has a practical wraparound period far beyond system lifetime. The relevant issue is therefore not overflow but interpretation and synchronization.

## Scheduler signalling

`pit_irq` performs only two logical operations:

```text
++ticks;
proc_on_tick();
```

`proc_on_tick` sets global `g_slice = 1`. It does not save process registers, select another process, write CR3 or enter a different user task from the interrupt handler.

Other code can query `proc_slice_due()` and later clear the signal with `proc_slice_ack()`. This is a deferred scheduling model: the timer says that a scheduling boundary is due, while the actual safe point that consumes that request is elsewhere.

The distinction reduces the amount of work performed at interrupt level and avoids embedding all scheduler policy in an IRQ callback.

## What a full preemptive scheduler would require

A general preemptive scheduler must preserve the complete execution context of the interrupted task, update task state, select a runnable target, potentially switch page-table roots, choose the target kernel/user stack state, restore target registers and return to the target context.

On SMP it also requires a concurrency model for run queues and per-CPU current-task state. If user tasks can run on multiple CPUs, process address-space transitions and TLB semantics become part of scheduling correctness.

The current `g_slice` flag is much simpler. It should not be documented as a full preemptive scheduler merely because it is set from a timer interrupt.

## Relationship to desktop cadence

The boot code reports “desktop 60Hz” before entering `desktop_run`. The PIT frequency and desktop loop therefore share a nominal cadence, but the source should be read carefully: the PIT interrupt and the desktop rendering loop are different mechanisms. A 60 Hz periodic timer can provide time/slice signals while graphics presentation follows its own scheduling and workload.

A robust documentation model should avoid equating display refresh, animation update rate and PIT IRQ frequency unless source explicitly couples them.

## Timing units

At the current fixed frequency, software can convert tick counts approximately:

```text
seconds ≈ ticks / 60
milliseconds ≈ ticks * 1000 / 60
```

Integer calculations must consider truncation. For deadlines it is usually safer to compare differences in tick space than repeatedly convert to milliseconds. Unsigned modular subtraction also makes wraparound handling more tractable, although wraparound is not practically imminent for a 64-bit 60 Hz counter.

The present PIT interface exposes only raw ticks, which leaves unit policy to higher layers.

## Latency and jitter

The PIT asserts periodically, but handler execution is not guaranteed at the exact ideal instant. Interrupts can be disabled; a higher-priority or non-maskable event can intervene; emulation can pause the vCPU; long critical sections can delay service.

Therefore one tick represents “one periodic timer interrupt was handled,” not an exact statement that precisely 16.6667 ms of wall time elapsed between every pair of handler executions.

For a real-time design, latency distribution, worst-case interrupt masking and clocksource stability would require measurement. ChrisOS currently does not claim hard real-time scheduling from the PIT.

## Interaction with interrupt masking

`pic_init` initially masks every legacy IRQ. `pit_init` specifically unmasks IRQ0. Later global `sti` allows maskable interrupts at the CPU level.

The state of a PIC mask bit and the IF flag are independent layers. An unmasked IRQ0 cannot enter while IF is clear. Conversely, setting IF does not make a PIC-masked line deliver.

ChrisOS uses this distinction during boot: devices/controllers can be configured while global interrupts remain disabled, then enabled at a deliberate point after sensitive initialization.

## Interrupt-storm policy

The generic IRQ dispatcher applies a cumulative 10,000-hit storm mask to IRQs greater than zero. IRQ0 is exempt. Without that exception, a healthy 60 Hz timer would cross 10,000 events in roughly 166.7 seconds and be incorrectly disabled.

The explicit exemption is evidence that the timer is expected to run indefinitely and at high count relative to event-driven device IRQs.

## Concurrency and memory ordering

The tick and slice flag are simple globals. In the current BSP-constrained process model this is adequate for their limited role. They are not a general SMP timer accounting framework.

If another CPU consumes `ticks` or `g_slice` with strong ordering requirements, `volatile` alone is not a substitute for atomics or locking. Similarly, a future per-CPU scheduler should generally avoid one global slice flag because timer events and runnable state need CPU ownership.

The documentation therefore distinguishes “works in current execution model” from “sufficient abstraction for an SMP scheduler”.

## Failure modes

`pit_init` can fail because frequency is zero, divisor computes to zero, or divisor exceeds 16 bits. `kstart` treats failure as fatal because the current system expects its timer cadence.

Programming the wrong access mode or byte order can produce an unexpected period. Forgetting to unmask IRQ0 produces no ticks. Forgetting to install the handler before unmasking risks dispatch with no timer callback. Failure to send EOI can cause the PIC to stop delivering subsequent events. Keeping IF clear prevents delivery even though the PIT continues running electrically or virtually.

In virtual machines, PIT emulation accuracy and host scheduling can add timing irregularity that is not visible from the divisor alone.

## Alternatives and architectural evolution

Modern x86 systems offer LAPIC timers, HPET and invariant TSC-based timekeeping. These can separate a high-quality clocksource from per-CPU clock events and reduce dependence on legacy PIC/PIT hardware.

ChrisOS already has LAPIC infrastructure but does not currently document a LAPIC timer implementation in the reviewed code. Migration should not be represented as complete until source, calibration strategy and validation gates exist.

A future timing architecture should explicitly distinguish:
- clocksource: monotonically measures elapsed time;
- clock event device: schedules future interrupts;
- scheduler accounting;
- sleep/timeout queues;
- user-visible wall clock.

The current PIT abstraction combines only a periodic clock event with a raw tick counter and slice signal.

## Validation

Direct source evidence includes input frequency constant, divisor checks, control word, two-byte channel write, handler registration, IRQ0 unmask, tick increment and slice flag.

Runtime validation can count interrupts over a known interval, verify monotonic `pit_ticks`, ensure IRQ0 remains active beyond 10,000 events, test periods with IF temporarily cleared, and measure jitter under I/O/SMP load. Scheduler validation should separately prove where and how `proc_slice_due` is consumed.

## Current limitations

The timer is fixed at boot to 60 Hz, uses legacy PIT/PIC delivery, exposes only a raw tick count and global scheduling flag, and does not provide a calibrated nanosecond clocksource or per-CPU clock events. It is sufficient for the present kernel cadence but is not a complete modern time subsystem.

## Source map

`kernel/metal/pit.c`/`pit.h` implement programming and counting. `kernel/metal/irq.c` supplies vector-to-IRQ dispatch and EOI. `kernel/metal/proc.c` owns the slice flag. `kernel/metal/start.c` chooses 60 Hz and defines the boot ordering. The Source Atlas includes every file in full at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
