---
id: kernel-jobs-kthreads
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/job.c
  - kernel/metal/job.h
  - kernel/metal/kthread.c
  - kernel/metal/kthread.h
  - kernel/metal/spin.c
  - kernel/metal/spin.h
  - kernel/metal/smp.c
  - kernel/metal/smp.h
  - kernel/metal/tlb_proto.c
  - kernel/metal/tlb_proto.h
symbols:
  - job_init
  - job_submit
  - job_worker_once
  - job_worker_forever
  - job_wait_idle
  - kthread_create
  - kthread_join
  - kt_run
  - spin_lock
  - spin_unlock
depends_on:
  - interrupts-smp
  - atomics-memory-model
related:
  - tlb-shootdown
  - process-lifecycle
---

# Kernel jobs and cooperative kernel threads

## Scope

ChrisOS has two related execution mechanisms that must not be conflated with a conventional preemptive kernel scheduler. The job layer provides a bounded multi-producer work queue consumed by the BSP or application processors. The kthread layer builds a cooperative “thread-like” abstraction on top of that job system by assigning each kthread a private stack and running a callback to completion on whichever worker executes its job.

The model is useful for parallel kernel work while keeping process scheduling simpler. It also carries strict semantics: a kthread callback must return, there is no timer-driven kthread preemption, kthread identity is a fixed slot rather than a process/task object, condition variables are sequence-based busy waits, and process context switching remains BSP-only.

This chapter documents queue state, locking, per-CPU execution, stack switching, fallback behavior, join semantics, TLS slots, synchronization primitives and the interaction with TLB fencing.

## Job queue structure

The job layer defines:

```c
#define JOB_QUEUE_CAP 1024u

typedef void (*JobFn)(void *arg, uint32_t cpu_index);

typedef struct {
    JobFn fn;
    void *arg;
} Job;
```

The queue is a fixed static ring of 1,024 entries. Global state stores head, tail and count. A `Spinlock` protects those structural fields. Two additional atomic counters track completed work and in-flight work.

There is no heap allocation in `job_submit`. The caller supplies a function and opaque argument; the queue copies only those two machine-level values into the next slot. This avoids allocation failure inside the queue path but also means argument lifetime is a caller responsibility.

A job argument must remain valid until the worker invokes the callback. Passing a pointer to a stack object that returns before execution would create a use-after-scope error even though the queue itself is correct.

## Spinlock implementation

`Spinlock` contains one volatile 32-bit word. `spin_lock` loops on a compare-and-swap from 0 to 1 and executes `pause` after a failed attempt. `spin_unlock` uses the compiler builtin release operation.

`atomic_add_u32` is implemented with `__sync_fetch_and_add`. The job layer uses it for `g_inflight` and `g_completed`, allowing these counters to be updated by multiple CPUs without a separate queue lock.

The lock protects ring structure; the atomic counters represent cross-CPU accounting. The distinction avoids holding the queue lock while actually executing a callback.

`spin.h` also defines `irq_save`/`irq_restore` helpers, but the basic job queue lock itself does not automatically disable interrupts. Callers must therefore understand whether the same lock can be acquired in interrupt context. The current job queue is driven from worker loops rather than directly from an IRQ callback.

## Initialization

`job_init` initializes the spinlock and resets head, tail, count, completed and in-flight state.

It is called in `kstart` after graphics/APIC/IOAPIC initialization and before `smp_init`. This order matters because APs enter `job_worker_forever` as part of their bring-up; the queue must already be valid before an AP can consume it.

## Submission

`job_submit(fn, arg)` rejects a null callback by returning 0. It then acquires the queue lock. If the ring is full, it unlocks and returns 0.

Otherwise it writes the function and argument at `g_q_tail`, advances tail modulo 1,024, increments count and atomically increments `g_inflight`. The lock is released before any worker executes the callback.

The return convention is boolean-like: 1 means accepted, 0 means not queued. Queue-full is backpressure, not a panic.

This is an important API property because kthreads use a fallback when the queue cannot accept their job, while the SMP self-test actively drains work and retries submissions.

## Worker consumption

`job_worker_once(cpu_index)` first checks whether the CPU has been fenced by the TLB protocol. If so, it polls TLB state, marks itself halted and returns without taking new work.

Otherwise it polls pending TLB invalidation before touching the queue. This gives memory-coherency work priority over ordinary queued jobs.

The worker initializes a local empty job, acquires the queue lock, removes one entry from head if available, decrements count, releases the lock, and only then calls the callback.

After callback completion it atomically increments `g_completed` and decrements `g_inflight`.

Executing outside the lock is essential. A callback may take a long time, submit more work or use other locks. Holding the ring lock across execution would serialize all workers and could deadlock recursive submission.

## Persistent AP workers

`job_worker_forever(cpu_index)` is the steady-state execution loop used by application processors. It repeatedly:

- checks TLB fencing;
- if fenced, performs TLB handling, marks the CPU halted and enters permanent `cli`/`hlt`;
- after the BSP releases AP interrupts, enables the Local APIC unless disabled by boot flag, executes `sti` once and remembers that IRQs are enabled;
- consumes one job;
- executes `pause`.

The loop is intentionally simple and polling-oriented. There is no sleeping run queue or wakeup IPI for jobs. Idle APs consume cycles executing `pause`, which is friendlier to SMT/power behavior than a tight ordinary loop but is not equivalent to halting until work arrives.

## Delayed AP interrupt enablement

`smp_release_ap_irqs` sets a global flag. AP workers notice it on their next loop and enable local interrupts exactly once.

The source explains the sequencing constraint: enabling LAPIC/IF during an ATA copy previously prevented the copy from finishing. Consequently APs are brought online as workers while IF remains clear, and asynchronous interrupt participation is released later by the BSP.

That is a concrete boot-state transition: “CPU online for jobs” and “CPU accepting ordinary maskable interrupts” are not the same moment.

## Waiting for global idle

`job_wait_idle` loops while `g_inflight != 0`. On each iteration it executes `job_worker_once(0)` on the BSP and then `pause`.

This gives the waiting BSP productive behavior: instead of only waiting for APs, it can drain queued work itself. It also makes the function work in a single-CPU system.

“In-flight” is incremented at successful submission and decremented after callback return, so it covers both queued and currently executing jobs. Waiting for zero therefore means no accepted job remains outstanding.

The counter does not identify which job belongs to which caller. `job_wait_idle` is a global barrier over this queue, not a scoped future/promise.

## SMP self-test

`smp_job_selftest` first skips when fewer than two CPUs are online. It submits 16 increment jobs, waits for idle and checks the resulting sum. It then performs 32 waves of 128 jobs each.

If submission finds a full queue during the test, the BSP executes `job_worker_once(0)` and retries, with a bounded retry counter that panics if progress cannot be made.

The test verifies basic queue consumption, atomic increment behavior and multi-worker progress. It does not prove arbitrary callback safety, fairness or absence of starvation.

## Kthread object model

The kthread layer defines a static array of 32 slots. Each slot stores:

- `used`;
- volatile `done`;
- function and argument;
- eight generic TLS pointers;
- allocated private stack;
- saved caller RSP.

Every stack is 32 KiB (`KT_STACK = 32768`), allocated from the kernel heap.

A kthread is therefore not a process and not a hardware thread. It is a kernel callback plus a dedicated stack, executed cooperatively through the job system.

## Per-CPU current state

Earlier designs with one global “current kthread” and saved stack would be unsafe under SMP: two CPUs running kthreads simultaneously could overwrite each other's return stack state.

The current implementation uses arrays indexed by CPU:
- `g_cur_cpu[SMP_CPU_CAP]` stores the current kthread slot id;
- `g_run_cpu[SMP_CPU_CAP]` stores the kthread object used by the trampoline.

`kt_cpu` calls `smp_current_cpu` and bounds the result. CPU identity itself is derived from the AP stack address range, not from a shared LAPIC register read.

This per-CPU split is a direct concurrency invariant. Stack restoration data that belongs to one CPU must never be consumed by another.

## Private-stack execution

`kt_run` computes the aligned top of the allocated kthread stack. It saves the current RSP into the kthread object, switches RSP to the private stack, calls `kt_trampoline`, then restores the original RSP after the callback returns.

The assembly declares volatile register clobbers and memory effects so the compiler does not assume state survives incorrectly.

The trampoline obtains the running kthread from `g_run_cpu[current_cpu]` and calls its function.

Because control returns normally to `kt_run`, the callback must return. There is no independent scheduler context capable of resuming a function that voluntarily yielded at an arbitrary point.

## Creation

`kthread_create(fn, arg)` rejects null functions. It acquires a slot lock, finds a free kthread entry, marks it used and initializes basic fields, then releases the lock.

Stack allocation occurs after slot reservation. If `kmalloc(32768)` fails, the slot is returned to the free pool.

Once a stack exists, the function attempts to submit `kt_job` to the job queue. If the queue is full, it does not fail the kthread creation. Instead it executes the kthread immediately on the current CPU using the same private-stack path, marks it done and returns its slot id.

This fallback gives a strong progress property under queue saturation, but it changes timing: a nominally asynchronous creation may execute the entire callback synchronously before `kthread_create` returns.

Callers must not assume creation always returns before the function body runs.

## Completion and join

`kt_job` installs the current slot id for the executing CPU, runs the private-stack callback, sets `done = 1` and restores the previous current id.

`kthread_join(id)` waits until `done` becomes true. Its behavior differs by CPU topology:

- with only the BSP online, join actively calls `job_worker_once` so the queued kthread can run;
- with APs online, join only executes `pause` and leaves arbitrary queued jobs to worker CPUs.

The source comment explains the choice: pulling unrelated jobs into a waiter under SMP can introduce unexpected reentrancy.

After completion, join acquires the slot lock, detaches the stack and clears slot state, then frees the stack outside the lock.

A joined kthread id is therefore reusable. Code must not retain the id as a stable lifetime identity after join.

## TLS

Each kthread has eight untyped pointer slots. `kthread_tls` and `kthread_tls_set` first resolve the current kthread id. Calls outside a kthread return no value/do nothing. Indexes outside 0–7 are rejected.

This is intentionally lightweight TLS, not ELF TLS, FS/GS-base TLS or language runtime thread-local storage. The kernel controls the small fixed array directly.

## KMutex

`KMutex` is a thin wrapper around `Spinlock`. `kmutex_lock` spins until acquired; it does not sleep the current kthread.

Calling it around long operations can therefore burn CPU and block progress of other work that depends on the same worker. It is suitable only where critical sections are expected to be short and lock ordering is controlled.

No owner tracking, recursion detection or priority inheritance exists in this primitive.

## KCond

`KCond` contains only a volatile sequence counter. Wait captures the current sequence, unlocks the associated mutex, then loops until the sequence changes. On UP it executes `job_worker_once` while waiting; on SMP it uses `pause`. It reacquires the mutex before returning.

`kcond_signal` increments the sequence counter.

This is not a queued condition-variable implementation with waiter lists. A signal changes a generation observable by all current pollers. There is no blocking scheduler primitive or one-waiter wake selection.

Users must still follow the normal condition-variable discipline of checking the protected predicate under the mutex, because a sequence change only says “a signal occurred”, not “your desired condition is now true”.

## Relationship with TLB fencing

Every worker loop checks TLB runtime state. The TLB protocol classifies CPUs as absent, online or fenced. A fenced CPU is removed from future online acknowledgement expectations, but physical-frame reuse remains forbidden until the protocol has evidence that the CPU flushed the relevant generation and halted.

Workers participate by polling and heartbeating through the memory layer. If fenced, they cease ordinary work.

This coupling prevents the job system from continuing to execute arbitrary kernel callbacks on a CPU that memory management has declared unsafe for continued participation.

## Process scheduling is separate

`proc_switch` explicitly panics if called from an AP. User process switching is BSP-only in the reviewed revision.

Therefore AP job execution must not be described as “process scheduling across CPUs”. APs execute kernel work items and kthread callbacks; user address-space scheduling remains a separate restricted mechanism.

This separation simplifies CR3 ownership and user-task state, at the cost of not yet distributing user processes across cores.

## Memory ownership

The job queue owns copies of function/argument values but not the pointed-to argument object. Kthread slots own their allocated stacks from successful creation through join cleanup.

The slot reservation and stack allocation are deliberately separated so allocation can happen outside the spinlock. Failure unwinds the slot state. Join similarly removes ownership under lock and performs `kfree` after releasing it.

Callbacks themselves own whatever resources their contract specifies; the kthread framework does not automatically clean arbitrary callback allocations.

## Failure and deadlock modes

Important hazards include:
- passing an argument whose lifetime ends before callback execution;
- waiting for a job while holding a lock that the job needs;
- using a kthread callback that never returns;
- creating lock-order cycles across AP workers;
- using KMutex for long blocking operations;
- assuming asynchronous creation when queue-full fallback can execute synchronously;
- joining the current kthread, which would wait for its own completion;
- retaining TLS or slot identity after join;
- continuing normal work on a CPU that the TLB protocol fenced.

The current primitives favor transparent source and bounded state over sophisticated deadlock prevention. Correct lock ordering remains a subsystem design responsibility.

## Performance characteristics

Queue operations are O(1) and touch one global spinlock. Under high submission/consumption concurrency that lock can become a contention point. Work execution is parallel once jobs leave the ring.

The 32 KiB stack per active kthread makes memory usage predictable: up to roughly 1 MiB for 32 stacks, excluding allocator overhead and slot structures.

Idle APs poll with `pause`, trading latency for CPU consumption. There is no work-stealing hierarchy, NUMA policy or affinity mechanism.

## Validation

The built-in SMP job self-test provides concrete multi-CPU queue evidence. Additional host tests in the source tree exercise kthread/SMP behavior and saturation-related primitives.

A comprehensive gate should test queue wraparound, exact full/empty boundaries, concurrent producers, nested submissions, synchronous fallback, join on UP/SMP, TLS isolation between CPUs, condition signalling, stack alignment, lock contention and TLB fencing while jobs are active.

The generated Source Atlas exposes the complete queue, kthread, spinlock, SMP and TLB-protocol sources for revision-bound review.

## Current limitations

This is a cooperative kernel-work model, not a preemptive kernel-thread scheduler. Kthreads do not yield/resume arbitrary call stacks, have no priority, no affinity API, no sleeping wait queues, no cancellation and no scheduler-owned run state beyond the job callback.

The model is nevertheless more than a function queue: private stacks and per-CPU current state allow complex kernel callbacks to execute with independent stack storage in parallel.

## Source map

Core queue logic is `kernel/metal/job.c`/`job.h`. Private-stack kthreads and synchronization wrappers are `kernel/metal/kthread.c`/`kthread.h`. Atomic/spin primitives are `kernel/metal/spin.c`/`spin.h`. AP lifecycle and CPU identity are `kernel/metal/smp.c`/`smp.h`. TLB fencing constraints come from `kernel/metal/tlb_proto.c`/`tlb_proto.h`. All are available in full in the Source Atlas at revision `da3df29cb397932c43d32373871fb9380e688ade`.
