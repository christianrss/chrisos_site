---
id: panic-logging
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/panic.c
  - kernel/metal/panic.h
  - kernel/metal/klog.c
  - kernel/metal/klog.h
  - kernel/metal/serial.c
  - kernel/metal/serial.h
  - kernel/metal/buildid.c
  - kernel/metal/buildid.h
  - kernel/metal/syscall.c
  - kernel/metal/start.c
symbols:
  - panic
  - panic_exception
  - panic_identity
  - klog_init
  - klog_putc
  - klog_puts
  - klog_copy
  - panic_user_fault
depends_on:
  - idt-exceptions
related:
  - validation-evidence
  - process-lifecycle
---

# Panic, serial diagnostics and kernel log

## Scope

Failure reporting in a kernel operates under worse conditions than ordinary application logging. The heap may be corrupted, interrupts may be unsafe, the filesystem may not be mounted, the display stack may be the failing subsystem, and the processor may be in an exception context. ChrisOS therefore keeps its fatal path small and uses serial output as the last-resort diagnostic channel. Separately, it maintains a fixed in-memory kernel log ring that does not allocate and can later be persisted to ChrisFS after storage initialization.

The current architecture also distinguishes a fatal ring-0 exception from a user-process fault. The former halts the machine; the latter can be recorded, contained to the process and returned to a kernel continuation.

## Serial as the bootstrap channel

`kstart` initializes serial before almost every other subsystem. If `serial_init` fails, the kernel disables interrupts and halts without attempting normal boot.

This ordering makes serial part of the diagnostic root. Boot information, memory-map validation, device status, panic identity and many self-test messages can be emitted without depending on graphics or filesystem state.

A low-level log path should have as few dependencies as possible. If it required the heap, filesystem or window manager, failures in those layers could make the diagnostic path recursively fail.

## Fatal panic

`panic(message)` is declared `_Noreturn`.

Its first instruction-level policy is to execute `cli`. Once the kernel decides it cannot safely continue, ordinary maskable interrupts must not re-enter partially broken state.

The function prints “PANIC: ”, the supplied message, then calls `panic_identity`. Finally it loops forever on `hlt`.

The loop has no recovery branch. This is an intentional fail-stop policy for fatal kernel invariants.

## Exception panic

`panic_exception(vector, error, rip)` is also non-returning. It disables interrupts, reads CR2, and reports:
- exception vector;
- hardware/normalized error value;
- saved RIP;
- CR2.

It then appends the same identity block and halts forever.

CR2 is always printed, even for exceptions where it is not semantically the faulting address. It is most important for #PF. The vector/error context lets later analysis interpret relevance.

## Identity record

`panic_identity` captures:
- CPU index via `smp_current_cpu()`;
- current CR3;
- current RSP;
- build ID;
- Git revision metadata;
- kernel SHA-256 string.

This turns a serial panic line into revision-bound evidence. A crash report that includes only “page fault” is weak; a report that identifies exact source/build and address-space root can be correlated with the binaries and generated documentation.

RSP helps identify which stack class was active. CR3 helps distinguish kernel versus process address space and diagnose stale or incorrect context switches.

## Why build identity belongs in a panic

Kernel debugging is highly sensitive to exact code layout. Even small commits move functions, change instruction offsets and alter timing.

The build metadata functions make it possible to answer “which kernel produced this crash?” before attempting symbolization or reproducing the issue.

The site documentation is also revision-bound. Matching a panic Git/build identifier to the documented revision prevents analysis against the wrong source state.

## Kernel log ring

`klog.c` defines an 8,192-byte static char array, write position, current length, spinlock and initialized flag.

`klog_init` initializes the lock and resets ring metadata. Repeated initialization is idempotent once ready.

The buffer is fixed storage. It does not allocate memory and does not touch the filesystem. Those are deliberate dependency constraints for a low-level log.

## Writing

`klog_putc` lazily initializes the log if needed, acquires the spinlock, writes at `g_pos`, advances the position modulo capacity and grows `g_len` until capacity is reached.

After the ring becomes full, new bytes overwrite the oldest bytes while length remains at 8,192.

`klog_puts` is simply repeated `klog_putc` until NUL.

Because each character acquires the lock independently, messages from concurrent writers can interleave at character boundaries if they call `klog_puts` simultaneously. The lock protects ring structural integrity, not atomicity of an entire string message.

## Reading the ring

`klog_copy(dst, cap)` rejects invalid destination, zero capacity or uninitialized state.

Under lock, it chooses `n = min(g_len, cap)` and computes the oldest retained byte as:

```text
start = (g_pos + KLOG_CAP - n) % KLOG_CAP
```

It then copies in chronological order, wrapping modulo capacity.

This is important: raw physical array order after wrap is not chronological. The start calculation reconstructs the logical log order.

The function returns byte count and does not append a NUL terminator. The consumer must treat it as a byte log, not assume C-string termination.

## Persistence after filesystem initialization

In `kstart`, after storage initialization, filesystem initialization and installation logic, the kernel checks whether the active backend is ChrisFS.

It creates a static 4,096-byte boot-log buffer and calls `klog_copy`. If bytes exist, it writes them to `SYS/BOOT.LOG`. Success/failure is reported on serial.

This produces a staged logging architecture:
- early diagnostics can exist in memory/serial before storage;
- once a filesystem is operational, a snapshot can be persisted.

Only up to 4,096 bytes are copied at this point even though the ring capacity is 8,192, so the persistence operation records at most the newest 4 KiB selected by `klog_copy` semantics.

## Relationship between serial and klog

Serial and klog are separate mechanisms. The reviewed source does not imply that every `serial_puts` automatically enters `klog` unless the serial implementation explicitly does so. Documentation must trace actual call paths rather than assume one unified logging fan-out.

The panic path shown in `panic.c` directly calls serial functions. This guarantees a fatal message does not depend on acquiring the klog spinlock or on log initialization.

If a CPU panics while another CPU holds `g_lock`, a panic implementation that required klog could deadlock. The direct serial path avoids that dependency.

## User faults are not kernel panic

`panic_user_fault` in `syscall.c` is named historically but has a different policy.

It records a `ProcFault`, destroys the process, logs RIP/CR2/error/CPU/build information, sets exit code -11 and rewrites the interrupt frame so execution returns to kernel code.

It does not call `panic` and does not enter the global halt loop.

This distinction is one of the most important reliability boundaries in the current kernel: malformed user memory can terminate one process instead of unconditionally stopping the operating system.

## What still causes fatal halt

`irq_dispatch` sends remaining processor exceptions below vector 32 to `panic_exception` after demand-page and user-fault handling.

Therefore an unresolved ring-0 page fault, invalid opcode in kernel, protection fault in privileged code and similar conditions remain fail-stop.

This is reasonable for an experimental kernel where continuing after an unknown violated invariant could corrupt state further. Recovery mechanisms should only be added where invariants and restart boundaries are explicit.

## Concurrency

The serial driver and klog have different concurrency properties. Klog ring mutation is protected by a spinlock. Panic disables local interrupts but does not automatically stop every other CPU before printing.

On SMP, multiple processors could attempt serial diagnostics simultaneously unless the serial layer serializes output. Panic identity includes CPU number so interleaved reports can at least be attributed.

A mature global panic protocol often elects one panic CPU and stops/fences others before producing a coherent dump. ChrisOS already has NMI-based CPU stopping machinery for TLB fencing, but the reviewed panic code does not claim a full SMP panic-stop protocol.

## Failure-path dependency graph

The intended dependency direction is:

```text
fatal condition
    |
cli
    |
serial output
    |
register/build identity
    |
hlt loop
```

It intentionally excludes:
- heap allocation;
- filesystem writes;
- graphics/window manager;
- scheduler recovery;
- user-space services.

The ordinary klog path can later interact with the filesystem during normal boot, but the fatal path remains minimal.

## Observability and reproducibility

Diagnostic fields should be sufficient to connect a crash to:
- exact revision;
- CPU;
- active CR3;
- instruction pointer;
- exception vector/error;
- page-fault address when relevant;
- stack pointer.

The reviewed panic exception output provides most of these.

A future symbolized backtrace would add call-chain information, but reliable unwinding requires frame/unwind metadata and safe stack memory; it should not be faked from a single RIP.

## Security implications

Logs can contain addresses and build identifiers. In a development kernel this is useful, but a hardened multi-user system would consider whether exposing kernel virtual addresses or hashes to unprivileged consumers weakens address-space randomization or reveals sensitive state.

Current serial output is a privileged/debug channel, not a user-facing sanitized logging API.

The fixed ring also overwrites old data rather than growing without bound, preventing logging from exhausting heap or disk during repetitive errors.

## Performance

`klog_putc` takes a spinlock for every character. This prioritizes simplicity and correctness of the ring over high-throughput structured logging.

At high log volume on SMP, lock contention and character-level serial I/O can heavily perturb timing. Debug logs should therefore not be treated as performance-neutral.

A future system can buffer per CPU and merge records, but that would add ordering/timestamp complexity.

## Validation

Fatal-path validation should use controlled test builds or emulation:
- invoke `panic` and verify IF is cleared and CPU halts;
- trigger a known kernel exception and verify vector/error/RIP/CR2/build fields;
- fill/wrap klog and verify chronological copy;
- copy with capacity smaller than ring length;
- write boot log after ChrisFS becomes active;
- trigger a user fault and verify process-only termination;
- generate concurrent klog writers and verify ring metadata remains valid.

Validation should also confirm build ID/hash correspond to the binary under test.

## Current limitations

There is no structured severity/facility schema in `klog`, no timestamps in the ring record, no whole-message atomicity, no full SMP panic coordinator, no stack unwinder and no persistent crash dump generated by the fatal path.

The existing design provides a robust minimal base: early serial, revision identity, fail-stop fatal handling, bounded allocation-free ring logging and later boot-log persistence.

## Source map

Fatal handling is `kernel/metal/panic.c`/`panic.h`. The ring is `kernel/metal/klog.c`/`klog.h`. Transport is `kernel/metal/serial.c`/`serial.h`. Revision fields come from `kernel/metal/buildid.c`/`buildid.h`. User-fault containment is in `kernel/metal/syscall.c`, and boot persistence is wired in `kernel/metal/start.c`. All are mirrored completely in the Source Atlas for revision `da3df29cb397932c43d32373871fb9380e688ade`.
