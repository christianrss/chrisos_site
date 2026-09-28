---
id: atomics-memory-model
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/spin.h
  - kernel/metal/spin.c
  - kernel/metal/job.c
  - kernel/metal/smp.c
  - kernel/gfx/ac97.c
  - kernel/metal/mm.c
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/chriscpu.c
symbols:
  - cas_u32
  - atomic_add_u32
  - spin_lock
  - spin_unlock
  - job_submit
  - job_wait_idle
  - smp_init
  - ac97_on_irq
  - ac97_arm_waiter
  - ac97_take_event
  - emit_sync_cas
  - emit_sync_add
  - emit_sync_release
  - lock_ok
depends_on:
  - coherence
  - cache-hierarchy
  - cpu-datapath-isa
related:
  - interrupts-smp
  - spinlocks
  - tlb-shootdown
---

# Atomic operations and the memory model

## Scope: correctness after coherence

Cache coherence answers how multiple agents keep copies of one coherent memory block compatible. It does not, by itself, define every order in which a program's memory operations may become observable.

This chapter studies the next layer: **atomicity and memory ordering**. The primary architectural target is x86-64 using ordinary cacheable write-back memory, because that is the environment in which the current native ChrisOS synchronization code runs. Device memory, write-combining regions, persistent-memory instructions and non-temporal accesses have additional rules and must not be inferred from the write-back examples below.

A memory model constrains the executions a processor is allowed to expose. It is intentionally weaker than the naive rule "every core performs every load and store globally in source-code order." Modern processors overlap work, buffer stores, speculate, forward data and execute internally out of order. Correct architecture permits these optimizations while restricting the externally observable results.

![Memory-ordering layers and an x86-style store buffer](../../assets/diagrams/atomics-memory-model-en.svg)

There are at least four contracts in a systems program:

| Layer | What it constrains | ChrisOS example |
|---|---|---|
| Source-language/compiler model | which transformations the compiler may perform | volatile, GCC __sync builtins, GCC __atomic builtins |
| ISA memory model | which machine-level observations are allowed | x86 ordering, LOCK, MFENCE |
| Coherence | ownership and values for individual cache lines | shared lock word |
| Software protocol | legal application/kernel states | spinlock, event publication, queue ownership |

A correct lock must satisfy all four layers. Fixing only one is insufficient.

## Program order is not necessarily visibility order

Consider one processor:

~~~text
store X = 1
load  r = Y
~~~

In program order, the store is first. A typical x86 implementation may place the store into a store buffer while the load of a different address proceeds. Another core can therefore observe an execution that looks as though the later load occurred before the earlier store became globally visible.

This does **not** mean x86 arbitrarily reorders everything. For ordinary write-back memory, its model is comparatively strong. The architectural documentation constrains, among other things, the ordering of loads with loads, stores with stores, causality and locked operations. The main relaxation exposed by the common Total Store Order abstraction is that a load may pass an older buffered store to a **different** address.

A store buffer serves several purposes:

1. retirement of a store need not wait for ownership and lower-level completion;
2. later independent work can proceed;
3. a load from the same address can obtain the processor's own newest buffered value through store-to-load forwarding;
4. stores can drain to coherent memory later while preserving their required order.

TSO is an architectural abstraction, not a requirement that a physical processor literally contain one FIFO with exactly the teaching behavior used here.

## The Store Buffering litmus test

The classic two-processor test begins with X = 0 and Y = 0.

~~~text
CPU0                 CPU1
X = 1                Y = 1
r0 = Y               r1 = X
~~~

Under a strict sequentially consistent machine, the result r0 = 0 and r1 = 0 is impossible. At least one store would have to become globally ordered before the opposite load.

Under x86-style TSO, both processors can temporarily retain their own stores in private store buffers:

~~~text
CPU0 buffer: X=1     CPU1 buffer: Y=1
CPU0 reads Y=0       CPU1 reads X=0
later: X and Y drain to memory
~~~

Therefore the 0/0 result is allowed for ordinary memory. This is not a coherence failure: each location still has one coherent value history. It is an ordering effect between operations on different locations.

The reproducible checker shipped with this chapter explores all interleavings of a small TSO machine and confirms that the Store Buffering 0/0 outcome exists.

## Message passing and FIFO store order

Now consider a producer publishing data and then a flag:

~~~text
initially DATA = 0, READY = 0

producer                 consumer
DATA = 42                r0 = READY
READY = 1                r1 = DATA
~~~

For normal write-back memory in the simplified x86-TSO model, stores from one processor become visible in program order. If the consumer reads READY = 1 and then reads DATA, it must not obtain the old DATA = 0 merely because the producer's later READY store overtook its earlier DATA store.

This property is one reason acquire/release publication often requires no extra hardware fence for simple loads/stores on x86. The compiler still needs to preserve the source-language synchronization semantics, and other architectures can require explicit instructions.

The conclusion must remain scoped: device memory, weak memory types, non-temporal stores and specialized instructions can require different treatment.

## Sequential consistency versus TSO

**Sequential consistency (SC)** can be defined as an execution for which all memory operations appear in one total order that:

1. contains every memory operation from every processor; and
2. preserves each processor's program order.

SC is conceptually simple but restricts implementations strongly.

**Total Store Order (TSO)** preserves much of that structure while permitting stores to wait in a per-processor buffer. Loads can bypass older stores to different addresses, but a load must observe its own latest pending store to the same address. Stores drain in order.

The following table summarizes the teaching model, not every special x86 memory type:

| Pair in one processor | Ordinary x86/WB intuition |
|---|---|
| Load → Load | preserved |
| Load → Store | preserved |
| Store → Store | preserved |
| Store → Load, different address | may appear reordered because the store remains buffered |
| Store → Load, same address | forwarding preserves the processor's own newest value |

Architectural manuals remain authoritative when an instruction or memory type has special semantics.

## Atomicity is not the same as ordering

An operation is **atomic** if observers cannot see an impermissible intermediate state of that operation. Ordering specifies relationships between that operation and other operations.

A naturally aligned ordinary load can be atomic at its width without being a full memory barrier. Conversely, a fence can order operations without changing a value.

This distinction matters for read-modify-write operations:

~~~text
old = *p
new = old + 1
*p = new
~~~

Three source-level operations are not an atomic increment. Two processors can both read the same old value and overwrite each other.

An atomic RMW instead has one indivisible architectural modification order:

~~~text
atomic_fetch_add(p, 1)
~~~

The implementation obtains the required exclusive coherence permission and commits one atomic change relative to competing atomic accesses.

Width, alignment, cacheability and instruction choice matter. Software must use the architectural guarantees for the exact operation rather than assuming that every memory access is atomic simply because it fits in a machine word. Split accesses and device memory require particular caution.

## LOCK-prefixed operations

On x86, eligible instructions with the LOCK prefix perform an atomic read-modify-write on a memory destination and have strong ordering semantics. Intel documents a total order among locked instructions and prevents ordinary loads/stores from being reordered across locked instructions.

Modern cacheable-memory implementations generally obtain exclusive ownership of the relevant cache line rather than electrically locking a global external bus for every operation. The architectural contract is atomicity and ordering; the internal mechanism is implementation-dependent.

ChrisOS's self-hosted toolchain currently emits two important forms:

~~~text
lock cmpxchg dword [rcx], edx
lock xadd    dword [rcx], eax
~~~

ChrisAsm recognizes corresponding 32-bit and 64-bit forms. KCC uses them for its supported __sync compare-and-swap and fetch-and-add builtins.

A locked instruction can be substantially more expensive under contention because ownership of the line must move among cores. Atomic does not mean free.

## XCHG with memory

x86 gives XCHG with a memory operand atomic behavior even without an explicit LOCK prefix. That architectural special case is important for emulator design.

The current ChrisCPU do_xchg implementation is a functional sequence:

~~~text
read register
read r/m operand
write register
write r/m operand
~~~

With only one guest vCPU, another guest CPU cannot interleave into that sequence. Once ChrisCPU gains guest SMP, however, memory XCHG must become one guest-atomic transaction rather than several independently interleavable host operations.

The same reasoning applies to LOCK-prefixed arithmetic. The current interpreter accepts LOCK on a memory-form ALU instruction after lock_ok rejects register-only use, but then executes the ordinary read/compute/write path. That is sufficient only because direct ChrisCPU execution is currently single-vCPU. It is not an SMP implementation of LOCK.

## Compare-and-swap

Compare-and-swap (CAS) conditionally writes a new value if the old value matches an expected value.

~~~text
atomic CAS(p, expected, desired):
    old = *p
    if old == expected:
        *p = desired
        success
    else:
        failure
~~~

Its power comes from making comparison and update indivisible. Spinlocks, lock-free stacks and reference-state transitions can build on this primitive.

CAS does not solve every concurrency problem. Algorithms must still define:

- what state is protected;
- memory ordering on success and failure;
- progress behavior under contention;
- lifetime of objects referenced by the compared value;
- ABA hazards when a location changes A → B → A while identity matters.

A CAS loop can be correct atomically and still have poor scalability if many processors repeatedly request exclusive ownership of one line.

## Fetch-and-add

Fetch-and-add atomically increments a value and returns its previous value.

~~~text
old = atomic_fetch_add(counter, delta)
~~~

This supports unique ticket allocation, counters and reference accounting.

ChrisOS atomic_add_u32 wraps __sync_fetch_and_add. The job subsystem uses it for g_inflight, g_completed and the SMP self-test sum. The AP startup path also uses __sync_fetch_and_add to increment cpu_online_count.

These operations prevent lost updates to the increment itself. They do not automatically make every surrounding field part of one atomic transaction. Publication of additional data still depends on lock or memory-order protocol.

## Compiler barriers and CPU fences

The compiler and processor are separate reorderers.

A **compiler barrier** prevents selected compiler transformations but may emit no machine instruction. A common GCC-style form is:

~~~c
__asm__ volatile ("" ::: "memory");
~~~

The "memory" clobber tells the compiler that arbitrary memory may be affected, constraining motion of memory accesses across the statement. The CPU sees no fence instruction.

A **CPU fence** constrains architectural execution/visibility. Examples on x86 include LFENCE, SFENCE and MFENCE.

A CPU fence without compiler semantics can still be miscompiled if the source compiler moves operations around it. A compiler barrier without a CPU fence cannot impose hardware ordering that the ISA otherwise allows. Correct synchronization APIs need both aspects when both are required.

## LFENCE, SFENCE and MFENCE

For architectural memory-order purposes:

- **LFENCE** orders qualifying earlier loads before qualifying later loads; current processors also have documented dispatch-serialization behavior in specific contexts and configurations.
- **SFENCE** orders stores where its architectural rules require it, notably relevant to weakly ordered/non-temporal store cases.
- **MFENCE** orders earlier loads and stores before later loads and stores.

These instructions should not be inserted by intuition. Ordinary write-back x86 memory already supplies strong ordering, and locked operations already provide strong barriers. Redundant fences can increase cost without improving correctness.

MFENCE is currently listed as unsupported by ChrisCPU. PAUSE is likewise not implemented as a distinct guest instruction: F3 marks REP, and outside supported REP STOS behavior F3 90 effectively remains NOP in the current interpreter. This is a semantic gap for faithful execution of native spin loops.

## PAUSE is a spin-wait hint, not a memory fence

PAUSE tells x86 hardware that the processor is in a spin-wait loop. It can reduce penalties associated with exiting a tight loop and improve sharing of execution resources on implementations with simultaneous multithreading.

It does **not** acquire a lock, make a plain load atomic, publish data or replace a fence.

ChrisOS spin_lock executes PAUSE after a failed CAS:

~~~c
for (;;) {
    if (cas_u32(&lock->locked, 0u, 1u)) {
        return;
    }
    __asm__ volatile ("pause");
}
~~~

This reduces the aggressiveness of the wait, but every retry still performs a locked compare-and-swap. Under heavy contention, a test-and-test-and-set or queued lock can reduce coherence traffic by spinning on read-only state before attempting ownership. Whether such a change helps ChrisOS requires measurement and fairness requirements; it is not implied by the correctness model.

## Acquire and release

Acquire/release ordering is a software publication contract.

A **release** operation ensures that operations sequenced before it are not moved after the publication point in ways forbidden by the language model.

An **acquire** operation ensures that operations sequenced after it are not moved before the observation point in ways forbidden by the language model.

A typical handoff is:

~~~text
producer:
    write payload
    release-store READY = 1

consumer:
    r = acquire-load READY
    if r == 1:
        read payload
~~~

When the acquire observes the release (or the appropriate release sequence in the language model), the preceding payload writes become ordered before the consumer's following reads.

Acquire and release are directional. A release operation does not generally order later operations before itself; an acquire does not generally order earlier operations after itself.

## Relaxed, acquire, release, acq_rel and seq_cst

GCC __atomic builtins expose explicit order parameters derived from the C/C++ atomic model.

| Order | Purpose |
|---|---|
| relaxed | atomicity without inter-thread ordering beyond the atomic object's modification order |
| acquire | observation point for following operations |
| release | publication point for preceding operations |
| acq_rel | both directions for a read-modify-write |
| seq_cst | acquire/release plus participation in the language model's single sequentially-consistent order |

Sequentially consistent source atomics are stronger than merely "this machine instruction happens to be atomic." The compiler must preserve the language-level global constraints across all participating seq_cst operations.

On x86, acquire loads and release stores of ordinary cacheable memory can often lower to plain MOV instructions because the hardware model already supplies the necessary direction of ordering. The compiler still has to enforce the source semantics.

## GCC __sync builtins

The older __sync family predates the standardized C/C++ memory-order APIs. GCC documents most __sync operations as full barriers. The notable lock operations have directional semantics: __sync_lock_test_and_set is acquire-like and __sync_lock_release is release-like.

Current ChrisOS spin.c uses:

~~~text
__sync_bool_compare_and_swap
__sync_fetch_and_add
__sync_lock_release
~~~

The host/native compiler provides the intended builtin semantics.

The current KCC implementation is deliberately narrower:

| KCC builtin | Current lowering |
|---|---|
| __sync_bool_compare_and_swap on supported 32/64-bit pointers | LOCK CMPXCHG |
| __sync_fetch_and_add on supported 32/64-bit pointers | LOCK XADD |
| __sync_lock_release on supported 32/64-bit pointers | ordinary zero store |
| other __sync_* / __atomic_* builtins | outside the supported subset |

This is enough to generate the current basic spin primitive, but it is not a general implementation of the C atomic memory model.

## The KCC release-store boundary

KCC's emit_sync_release emits an ordinary zero store at the builtin call site. On x86 write-back memory, an ordinary aligned store is sufficient at the hardware level for a release unlock when previous critical-section stores have already been ordered before it.

However, a compiler implementation of release semantics also needs to prevent its own optimizer/scheduler from moving protected memory operations after the unlock.

The current KCC is a small direct emitter rather than a highly optimizing compiler, so its generated sequence is currently narrow and predictable. This should not be generalized into a permanent guarantee. If KCC gains more aggressive optimization, synchronization must become an explicit compiler IR/effect boundary rather than depending on the present emission strategy.

## volatile is not an atomic memory model

volatile asks the compiler to preserve observable accesses according to its volatile rules. It is essential for many MMIO registers and useful for polling implementation-specific state, but it does not provide:

- atomic read-modify-write;
- mutual exclusion;
- acquire/release synchronization;
- a total order among threads;
- a hardware memory fence.

KCC's tests correctly verify a narrower property: volatile loads and stores survive compilation at the intended width. That proves volatile access preservation, not inter-CPU synchronization.

This distinction matters because the current kernel contains volatile polling variables such as cpu_online_count and g_ap_irq_enable. Their current x86 behavior relies on a combination of implementation choices, aligned accesses, coherent hardware and surrounding atomic operations. They should not be used as evidence that volatile itself is an SMP primitive.

## Source analysis: cpu_online_count

cpu_online_count is declared volatile uint32_t. AP startup increments it with __sync_fetch_and_add, while the BSP polling loop performs repeated volatile reads.

At the hardware level on the current x86 target, this produces a practical polling pattern with atomic RMW writers and naturally sized reads. At the language-model level it is not the same design as declaring one C11 atomic object and using explicit atomic loads everywhere.

The distinction matters for future compiler evolution and portability. A more explicit design would specify the ordering required for AP initialization publication and use one atomic API consistently.

The chapter records the current implementation; it does not silently upgrade it into a stronger formal contract than the source states.

## Source analysis: AC97 event publication

The AC97 driver uses the newer __atomic builtins in several places.

In the IRQ handler:

~~~text
__atomic_fetch_add(&g_event_seq, 1, __ATOMIC_RELEASE)
...
waiter = __atomic_load_n(&g_ac97_waiter, __ATOMIC_ACQUIRE)
~~~

The waiter is published with:

~~~text
__atomic_store_n(&g_ac97_waiter, pid, __ATOMIC_RELEASE)
~~~

and the event sequence is consumed with an acquire load in ac97_take_event.

This is an explicit acquire/release vocabulary and is stronger documentation than volatile alone.

One subtle boundary is important: the release increment of g_event_seq occurs **before** later work in ac97_fill. Release orders operations before the release; it is not a promise that later writes have already been published when another CPU observes the sequence increment. Therefore the sequence increment must not be cited as publishing modifications that occur after it. If a future consumer requires those later effects, the publication point would need to be placed after them or the protocol would need another synchronization edge.

The current KCC does not support these __atomic_* forms, so this driver is also evidence that self-hosting the entire kernel requires expanding the compiler's atomic subset.

## Locks establish a happens-before-style protocol

For a conventional lock:

~~~text
CPU0:
    lock()
    write protected data
    unlock()

CPU1:
    lock()
    read protected data
    unlock()
~~~

Correct acquire/release semantics make the first critical section's protected writes visible to the second critical section after CPU1 successfully acquires the same lock.

The lock word alone is not the protected state. The ordering edge created by unlock/acquire is what allows ordinary non-atomic data inside the critical section to be safely communicated.

Using an atomic counter does not automatically protect a neighboring ordinary structure. Synchronization must be attached to the ownership protocol governing that structure.

## Interrupt disabling is not SMP synchronization

irq_save disables maskable interrupts on the **current CPU**. It prevents an interrupt handler on that CPU from re-entering a region, which is important for structures also used in IRQ context.

It does not stop another CPU.

Therefore code shared among CPUs and interrupt handlers can require both:

1. local interrupt control to avoid same-CPU IRQ re-entry; and
2. an inter-CPU lock/atomic protocol.

The PMM and AC97 paths demonstrate this composition. Treating CLI as a global lock would be incorrect.

## Memory ordering and MMIO

Device registers are not ordinary write-back RAM. Their memory type and bus semantics determine which accesses may combine, reorder or complete asynchronously.

Neither a C atomic operation nor MFENCE should be treated as a universal "device finished" instruction. Correct MMIO often also requires:

- the proper architectural memory type;
- width and alignment required by the device;
- device-specific readback or status polling;
- PCIe ordering/completion rules;
- DMA ownership and cache-coherence rules.

The next device chapters separate those concerns. This chapter's TSO litmus examples do not apply blindly to MMIO.

## Formalizing observations: po, rf and modification order

A useful intermediate formal vocabulary is:

- **po (program order):** order of operations in one thread/processor;
- **rf (reads-from):** which write supplied the value returned by a read;
- **modification order:** per-atomic-object total order of atomic writes/RMWs in the language model;
- **synchronizes-with:** a language-level edge created by operations such as a release observed by a matching acquire;
- **happens-before:** transitive ordering derived from sequencing and synchronization.

These concepts prevent ambiguous statements such as "the write happened first." First in source order, first in global visibility, first in modification order and first in wall-clock time are different claims.

For kernel reasoning, every publication protocol should identify the exact operation that publishes, the exact operation that observes, and the data whose visibility depends on that edge.

## Current ChrisCPU memory-order model

Direct ChrisCPU currently has a single guest vCPU. Its run loop executes one decoded instruction at a time. Guest RAM accesses ultimately become functional host reads/writes.

Consequently:

- there is no guest store buffer;
- there is no second guest CPU to observe reordering;
- there is no guest coherence directory or cache protocol;
- LOCK-prefixed memory ALU operations are not implemented as cross-vCPU atomic transactions;
- memory XCHG is not an SMP atomic transaction;
- CMPXCHG and XADD are not implemented by ChrisCPU even though ChrisAsm/KCC can emit them;
- MFENCE is unsupported;
- PAUSE has no dedicated spin-wait semantics.

The statement in the existing ChrisCPU documentation that a LOCK memory operation is "atomic relative to the guest" is true only in the trivial single-vCPU sense: there is no competing guest processor. It must not be interpreted as an x86 SMP validation.

## Requirements for an SMP ChrisCPU memory model

Before ChrisCPU can boot and validate the native SMP synchronization path, the emulator needs an explicit model rather than host-language accidents.

### 1. Define the architectural scope

Choose whether the first SMP model represents:

- sequential consistency;
- x86-style TSO for ordinary WB memory;
- or a more complete x86 memory-type model.

Starting with functional TSO is substantially simpler than starting with detailed cache timing.

### 2. Give each vCPU its own pending-store state

A deterministic TSO implementation can model a FIFO store buffer per vCPU.

~~~text
vCPU store:
    append address/value/width to own buffer

vCPU load:
    if newest matching own buffered store exists:
        forward from it
    else:
        read shared memory

drain event:
    commit oldest pending store to shared memory
~~~

The scheduler must permit drains at points that produce all architecturally allowed outcomes without inventing forbidden ones.

### 3. Implement locked transactions

LOCK CMPXCHG, LOCK XADD and memory XCHG must execute as indivisible guest transactions. A simple first implementation can use a global guest-memory lock while preserving architectural semantics. A later line-granular design can improve parallelism.

### 4. Implement fences

MFENCE must constrain store-buffer and load execution according to the chosen model. LFENCE and SFENCE need their documented scope. PAUSE can remain timing-neutral initially but should decode distinctly rather than pretending to be an ordinary NOP if fidelity is claimed.

### 5. Separate guest and host synchronization

If vCPUs run as host threads, host mutexes/atomics protect emulator data structures. They are implementation tools, not the guest memory model itself. The emulator must not accidentally promise stronger guest ordering merely because the host happens to be x86.

### 6. Add litmus tests

At minimum:

- Store Buffering: 0/0 allowed under TSO;
- Store Buffering with MFENCE: 0/0 forbidden;
- Message Passing: READY=1 with stale earlier DATA forbidden in the simple WB model;
- atomic increment: final count exact;
- CAS lock mutual exclusion;
- LOCK operations globally ordered;
- memory XCHG atomic;
- same-address store forwarding;
- TLB shootdown interaction across vCPUs.

The checker added to this documentation implements the first three at the abstract-model level.

## Reproducible TSO model

scripts/check_memory_model_examples.py implements a deliberately small state-space explorer.

Each processor has:

- a program counter;
- local registers used by litmus tests;
- a FIFO store buffer.

At each state, the explorer may either execute the next instruction of one processor or drain the oldest store from one processor's buffer. Loads consult the newest same-address buffered store before shared memory.

The explorer checks three claims:

1. Store Buffering can produce 0/0 without fences.
2. Inserting a fence between each store and load forbids 0/0.
3. In Message Passing, observing READY=1 and then DATA=0 is forbidden by FIFO store order plus preserved load order in this teaching model.

This is not a replacement for Intel/AMD validation. It makes the chapter's reasoning executable and reviewable.

## Correctness review checklist

When reviewing concurrent ChrisOS code, identify:

1. which object carries synchronization;
2. whether every writer uses the same protocol;
3. whether readers use matching atomic/lock operations;
4. required ordering: relaxed, acquire, release, full, or locked;
5. whether interrupt context participates;
6. whether another CPU can access the object;
7. whether DMA/device hardware participates;
8. alignment and width assumptions;
9. object lifetime while a reference is published;
10. whether the compiler understands the synchronization;
11. whether ChrisCPU can reproduce the relevant behavior;
12. whether a litmus or stress test covers the intended edge.

This checklist is more reliable than adding volatile or fences until a race disappears.

## Validation and revision limits

This chapter is reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Run:

~~~text
python scripts/check_memory_model_examples.py
~~~

The script proves properties only of its finite teaching model. It does not execute the kernel, measure native hardware, validate the full Intel or AMD memory model, or certify the compiler.

Existing KCC tests separately verify that its supported __sync builtins emit LOCK CMPXCHG, LOCK XADD and the release zero store. Existing ChrisCPU documentation and source establish the current single-vCPU and unsupported-fence limitations.

Changes to spin.c, job.c, smp.c, ac97.c, KCC atomic lowering, ChrisAsm locked instructions or ChrisCPU SMP execution should trigger review of this chapter.

## Primary references

- [Intel 64 and IA-32 Architectures Software Developer's Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html), System Programming Guide sections on memory ordering, locked operations and multiprocessor management.
- [AMD64 Architecture Programmer's Manual, Volume 2: System Programming](https://docs.amd.com/), Memory System sections on memory ordering and fences.
- [GCC __sync builtins documentation](https://gcc.gnu.org/onlinedocs/gcc/_005f_005fsync-Builtins.html).
- [GCC __atomic builtins documentation](https://gcc.gnu.org/onlinedocs/gcc/_005f_005fatomic-Builtins.html).
