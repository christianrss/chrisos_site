---
id: arrays-lists-stacks-queues
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - kernel/metal/job.h
  - kernel/metal/job.c
  - kernel/gfx/input.c
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_parse.c
symbols:
  - ClvmVm
  - clvm_vm_push64
  - clvm_vm_pop64
  - job_init
  - job_submit
  - job_worker_once
  - queue_push
  - input_next_event
  - Ast
  - ShComp
  - sh_parse
depends_on:
  - data-structures
  - recursion-recurrences-amortization
related:
  - bitmaps-rings-free-lists
  - systems-algorithms
  - chrisc-clvm
  - shader-frontend
---

# Arrays, linked structures, stacks and queues

<div class="abstract">
Arrays, linked structures, stacks and queues are the linear building blocks beneath schedulers, interpreters, parsers, device rings and event systems. Their asymptotic operations are simple, but systems correctness depends on representation details: contiguous versus indirect storage, fixed versus dynamic capacity, index and pointer validity, ownership, cache locality, overflow/underflow behavior, synchronization and memory ordering. This chapter develops those contracts and reconciles them with current ChrisOS source. CLVM uses bounded array-backed operand and call stacks; the kernel job subsystem uses a spinlock-protected circular queue of 1024 entries; the input subsystem uses a 64-slot ring that reserves one slot to distinguish full from empty and counts dropped events; and the shader parser stores AST nodes in a fixed array while chaining statement/argument sequences through integer next indices.
</div>

## Prerequisites and scope

The general data-structures chapter defines representation, invariants and cost models. The preceding amortization chapter explains geometric growth and sequence costs.

This chapter narrows the focus to four linear families:

- arrays;
- linked structures;
- stacks;
- queues/rings.

They can represent the same logical sequence while optimizing different operations.

A systems description must separate:

~~~text
abstract sequence semantics
        ↓
concrete representation
        ↓
capacity and ownership
        ↓
synchronization
        ↓
failure behavior
~~~

Calling something a queue is not enough to know whether it allocates, blocks, drops data, overwrites old entries or rejects insertion.

## Arrays

An array stores equal-sized elements contiguously.

For base address B, element size s and zero-based index i:

~~~text
address(A[i]) = B + i·s
~~~

This permits O(1) address calculation.

The formula is valid only when:

~~~text
0 <= i < length
~~~

and the multiplication/addition itself stays inside the address arithmetic contract.

## Array layout and locality

Contiguous storage provides strong spatial locality.

Sequential traversal:

~~~text
A[0], A[1], A[2], ...
~~~

tends to access nearby cache lines and is friendly to hardware prefetch.

This often makes arrays faster than pointer-linked structures even when both perform O(n) logical work.

The cost model should therefore include:

- element size;
- alignment and padding;
- cache-line occupancy;
- access order;
- write sharing between CPUs.

Big-O alone does not capture locality.

## Fixed-capacity arrays

A fixed array commits storage for a maximum number of elements.

Advantages include:

- no allocator dependency after initialization;
- stable element addresses;
- predictable memory footprint;
- straightforward bounds checks;
- deterministic saturation behavior if specified.

Disadvantages include:

- unused reserved space;
- hard maximum capacity;
- possible need for linear scans to locate free slots.

ChrisOS uses fixed arrays heavily in low-level paths where bounded memory is preferable to dynamic allocation.

## Dynamic arrays

A dynamic array usually stores:

~~~text
pointer
length
capacity
~~~

When length reaches capacity, it allocates a larger region and copies or moves elements.

Geometric growth gives amortized O(1) append, but one growth step remains O(n).

A resize may also:

- fail allocation;
- invalidate element pointers;
- change virtual/physical locality;
- require synchronization around pointer replacement;
- create a latency spike.

Those effects matter more in kernels and interrupt paths than the amortized bound alone.

## Insertion and deletion in arrays

Appending to a known free final slot is O(1).

Inserting into the middle requires shifting a suffix:

~~~text
[a b c d]
insert x at 1
[a x b c d]
~~~

The amount moved is proportional to the suffix length.

Deletion that preserves order similarly shifts later elements left.

If order does not matter, deletion can sometimes be O(1) by moving the final element into the deleted slot. That changes sequence order and therefore requires a different semantic contract.

## Sparse versus dense index spaces

An array is ideal when valid identifiers form a dense bounded interval.

If IDs are sparse, a direct array may waste memory.

Systems code often maps:

- CPU IDs;
- descriptors;
- object handles;
- AST node indices;
- opcode values;

into arrays when the domain is sufficiently dense.

The validity of the index is separate from whether the slot currently contains a live object.

## Linked structures

A linked structure stores relationships between elements rather than relying solely on contiguous position.

A singly linked node typically contains:

~~~text
payload
next
~~~

A doubly linked node adds:

~~~text
prev
~~~

Insertion after a known node can be O(1), but locating that node may already have required O(n) traversal.

Complexity claims must identify which reference is provided to the operation.

## Pointer-linked lists

In a pointer-linked list, next and prev are memory addresses.

Advantages:

- stable node addresses when nodes are individually allocated or embedded;
- O(1) splice when relevant node pointers are already known;
- natural support for intrusive linkage.

Costs:

- pointer storage;
- allocator or pool management;
- poor spatial locality when nodes are scattered;
- more cache/TLB misses;
- complex lifetime rules.

A stale pointer can turn a logical list error into memory corruption.

## Index-linked lists

A list can use array indices instead of pointers.

For example:

~~~text
nodes[i].next = j
~~~

where -1 represents no successor.

This representation combines:

- contiguous node storage;
- stable integer references while the array does not compact;
- explicit bounds checking;
- easier serialization than host pointers.

The cost is a fixed or separately managed node pool and an extra array indexing step for traversal.

## ChrisOS shader AST chains

Current shader parser state contains:

~~~text
Ast ast[SH_AST_MAX]
~~~

and each Ast contains:

~~~text
int16_t next
~~~

Parser routines such as parse_args, parse_block, parse_global_or_func and sh_parse build sequences by storing the next node index in ast[tail].next.

This is an index-linked sequence inside a fixed array.

It is not a heap-allocated generic linked-list library.

The distinction matters for:

- ownership;
- serialization;
- locality;
- capacity;
- invalid-index behavior.

node_new enforces the AST pool limit before creating another node.

## List invariants

For a singly linked sequence represented by indices, useful invariants include:

- head is -1 or a valid live index;
- every next is -1 or a valid live index;
- traversal reaches -1 if cycles are forbidden;
- every node appears at most once if uniqueness is required;
- tail.next = -1 when an explicit tail exists.

A list algorithm that assumes acyclicity can loop forever if the representation contains a cycle.

Cycle detection is therefore either an invariant guaranteed by construction or a validation problem.

## Traversal complexity

Traversing k linked nodes is O(k).

Random access to the i-th element is O(i) because the links must be followed from a known starting point.

This contrasts with O(1) array indexing.

Pointer chasing also weakens locality, although ChrisOS's index-linked shader AST keeps the backing nodes contiguous and therefore retains better memory density than separately allocated list nodes.

## Intrusive structures

An intrusive structure embeds linkage fields in the object itself.

Advantages:

- no separate node allocation;
- direct conversion from link to owner when layout is defined;
- fewer allocations and metadata objects.

The cost is coupling: an object needs separate linkage fields to participate independently in multiple collections.

Index-linked AST nodes are similar in spirit because the linkage is part of Ast itself, although the link is an integer index rather than a pointer.

## Stacks

A stack implements last-in, first-out order.

Abstract operations are:

~~~text
push(x)
pop()
top()
empty()
~~~

An array-backed stack stores an integer top or stack pointer.

A common representation is:

~~~text
storage[capacity]
sp = number of active elements
~~~

Then:

~~~text
push:
    require sp < capacity
    storage[sp] = x
    sp++

pop:
    require sp > 0
    sp--
    return storage[sp]
~~~

Both operations are O(1).

## Stack invariant

For capacity C:

~~~text
0 <= sp <= C
~~~

Active elements occupy:

~~~text
storage[0:sp]
~~~

The next free slot, when one exists, is storage[sp].

Overflow attempts must not write storage[C].

Underflow attempts must not decrement sp below zero.

These simple invariants are central because one off-by-one error directly becomes an out-of-bounds memory access.

## CLVM operand stack

Current ClvmVm contains:

~~~text
int64_t stack[CLVM_STACK_MAX]
uint16_t sp
~~~

where:

~~~text
CLVM_STACK_MAX = 256
~~~

clvm_vm_push64 checks:

~~~text
sp == CLVM_STACK_MAX
~~~

and rejects the push when full.

Otherwise it performs:

~~~text
stack[sp++] = value
~~~

clvm_vm_pop64 checks sp == 0 before:

~~~text
*value = stack[--sp]
~~~

The representation is a bounded array stack with explicit overflow and underflow signaling.

## CLVM call stack

ClvmVm separately contains:

~~~text
uint32_t calls[CLVM_CALL_MAX]
uint16_t csp
~~~

with:

~~~text
CLVM_CALL_MAX = 64
~~~

Operand values and return addresses therefore occupy different logical stacks.

This separation makes their bounds and failure modes independent.

A recursive guest workload can exhaust the call stack even when the operand stack still has space.

## Stack ownership and serialization

Because CLVM stacks are stored inside ClvmVm, the VM object owns their storage.

This has useful consequences:

- stack contents are part of explicit VM state;
- the VM can validate stack pointers during state restoration;
- guest nesting does not depend directly on host C stack depth;
- stack capacity is deterministic.

Current setjmp/longjmp support serializes active stack contents to VM memory and validates restored sp/csp bounds before applying them.

That is a concrete example of representation invariants crossing a state-save boundary.

## Queues

A queue implements first-in, first-out order.

Abstract operations:

~~~text
enqueue(x)
dequeue()
front()
empty()
~~~

A naive contiguous queue can remove element 0 by shifting all remaining elements, making dequeue O(n).

A circular array avoids movement.

## Circular queues

For capacity C, head and tail wrap with:

~~~text
next(i) = (i + 1) mod C
~~~

There are multiple valid full/empty conventions.

Two common forms are:

1. separate count:
   - empty when count = 0;
   - full when count = C;

2. reserve one slot:
   - empty when head = tail;
   - full when next(head) = tail;
   - usable capacity = C - 1.

The implementation contract must state which convention is used.

## Kernel job queue

Current kernel/metal/job.h defines:

~~~text
JOB_QUEUE_CAP = 1024
~~~

job.c stores:

~~~text
Job g_queue[JOB_QUEUE_CAP]
g_q_head
g_q_tail
g_q_count
Spinlock g_q_lock
~~~

This queue uses the separate-count convention.

job_init sets head, tail and count to zero.

job_submit takes g_q_lock and rejects insertion when:

~~~text
g_q_count == JOB_QUEUE_CAP
~~~

On success it writes at tail, advances tail modulo capacity and increments count.

job_worker_once takes the same lock, reads from head when count > 0, advances head and decrements count.

## Job queue invariants

Under operations protected by g_q_lock, intended invariants include:

~~~text
0 <= g_q_head < JOB_QUEUE_CAP
0 <= g_q_tail < JOB_QUEUE_CAP
0 <= g_q_count <= JOB_QUEUE_CAP
~~~

Modulo arithmetic preserves index range.

The count distinguishes full from empty, so all 1024 array slots are usable.

The lock serializes queue metadata mutations.

The job function itself runs after releasing the lock, which keeps user work outside the queue critical section.

## Job queue complexity

Ignoring lock contention:

- enqueue is O(1);
- dequeue is O(1);
- no element shifting occurs;
- memory use is O(JOB_QUEUE_CAP).

The queue has deterministic fixed memory.

When full, job_submit returns failure rather than allocating more space.

The caller must choose whether to retry, execute work locally or report failure.

Current self-test includes retry loops that run one worker step when submission temporarily fails.

## Input event ring

Current input.c defines:

~~~text
INPUT_QUEUE_CAPACITY = 64
InputEvent g_queue[INPUT_QUEUE_CAPACITY]
g_queue_head
g_queue_tail
g_lost_events
~~~

Unlike the job queue, it does not maintain a count.

queue_push computes:

~~~text
next = (head + 1) mod 64
~~~

and treats:

~~~text
next == tail
~~~

as full.

Therefore one physical slot is reserved to distinguish full from empty.

The usable event capacity is 63.

## Input queue saturation

When the input ring is full, queue_push increments g_lost_events and returns without storing the new event.

It does not overwrite the oldest event.

This is a drop-newest-style saturation behavior for this path.

That policy is semantically significant.

For user input, preserving older queued order while recording loss is different from overwriting the oldest event.

## Input dequeue

input_next_event returns false when:

~~~text
tail == head
~~~

Otherwise it copies the event at tail and advances tail modulo capacity.

Thus FIFO order follows the circular index progression.

input_clear_events sets tail to head, logically discarding every queued event without clearing the array bytes.

Logical membership therefore depends on indices, not stale data remaining in unused slots.

## Concurrency boundary of the input ring

The input ring differs from the spinlock-protected job queue.

The reviewed source uses volatile head/tail variables and compiler_barrier calls around publication/consumption.

It does not use g_q_lock-style mutual exclusion for this queue, nor does it present the structure as a generic portable lock-free queue.

Its correctness depends on the actual producer/consumer execution model and target memory-order behavior.

Documentation should therefore not upgrade “compiler barriers are present” into a universal lock-free or wait-free guarantee.

A full concurrency proof would need to specify:

- producer contexts;
- consumer contexts;
- CPU architecture;
- interrupt/preemption relationships;
- compiler and hardware ordering requirements.

## Ring wraparound

Modulo arithmetic means physical index order does not equal logical age.

Example with C = 8:

~~~text
head = 7
enqueue
new head = 0
~~~

The sequence remains FIFO because logical order is defined by traversal from tail to head with wraparound.

Debug tools must avoid assuming:

~~~text
tail <= head
~~~

in ordinary integer order.

That relation is false after wrap.

## Full versus empty ambiguity

If a ring stores only head and tail and allows all C slots to become occupied, then:

~~~text
head == tail
~~~

could mean either empty or full.

Implementations resolve this by:

- reserving a slot;
- keeping a count;
- using wider monotonic counters;
- storing generation bits.

ChrisOS demonstrates two of these choices:

- job queue: separate count;
- input ring: reserved slot.

Neither representation is universally superior.

## Memory ownership

Fixed array structures avoid per-element allocation, but ownership still matters.

Job queue:

- queue storage is static kernel state;
- Job holds function and argument pointers;
- queue ownership of the argument pointee is not established merely by storing the pointer.

Input queue:

- events are copied by value;
- consumer receives an InputEvent copy.

CLVM stack:

- values are stored by value inside ClvmVm.

Shader AST:

- node storage belongs to ShComp;
- next indices are valid only relative to that AST instance.

Confusing storage ownership with referenced-object ownership can produce lifetime bugs.

## Failure behavior

Linear structures require explicit saturation and empty policies.

| Structure | Empty behavior | Full behavior |
|---|---|---|
| CLVM operand stack | pop fails | push fails |
| CLVM call stack | call/return logic faults at bounds | call overflow fault |
| kernel job ring | worker does nothing | submit returns 0 |
| input ring | next_event returns false | new event dropped; loss counter increments |
| shader AST node pool | n/a | node creation fails with parser error |

These are implementation contracts, not generic properties of stacks or queues.

## Security implications

Bounds and lifetime errors in linear structures are common exploitation primitives.

Relevant failure classes include:

- array index out of bounds;
- integer overflow in index calculation;
- stack underflow/overflow;
- stale linked pointer or index;
- queue metadata race;
- use-after-free of queued pointer payload;
- capacity exhaustion used for denial of service;
- cyclic list causing unbounded traversal.

Fixed capacity limits memory growth but creates saturation surfaces that still require deliberate handling.

## Performance trade-offs

Arrays favor:

- compactness;
- sequential scans;
- cache locality;
- O(1) indexing.

Linked structures favor:

- stable nodes;
- local insertion/removal when position is known;
- flexible non-contiguous storage.

Stacks favor:

- constant-time LIFO;
- compact top-only mutation.

Rings favor:

- constant-time FIFO;
- fixed memory;
- no element relocation.

In systems code, representation is often chosen to bound allocator and latency behavior rather than minimize abstract operation count.

## Validation evidence

The chapter-specific deterministic checker validates:

- array address arithmetic;
- fixed-array bounds;
- index-linked-list traversal and cycle rejection in the model;
- bounded stack push/pop including overflow and underflow;
- separate-count ring behavior matching the job-queue convention;
- reserved-slot ring behavior with physical capacity 64 and usable capacity 63;
- FIFO preservation through wraparound;
- drop-on-full event behavior;
- current source anchors for CLVM_STACK_MAX, CLVM_CALL_MAX, JOB_QUEUE_CAP, job_submit/job_worker_once, INPUT_QUEUE_CAPACITY, queue_push/input_next_event, SH_AST_MAX and Ast.next.

The checker models documented structure invariants and verifies source anchors. It does not prove concurrent correctness of the input ring or all queue callers.

## Current limitations

This chapter does not fully cover:

- lock-free multi-producer/multi-consumer queues;
- hazard pointers or epoch reclamation;
- ropes, gap buffers and piece tables;
- persistent functional lists;
- deques in depth;
- vectorized container implementations;
- allocator internals;
- formal memory-order proofs.

Those topics belong to later specialized chapters.

## Roadmap boundary

The curriculum continues from linear structures into:

~~~text
arrays/lists/stacks/queues
      ↓
hash tables
      ↓
trees/heaps/tries
      ↓
graphs/union-find
      ↓
bitmaps/rings/free lists
      ↓
systems algorithms
~~~

Later chapters specialize the representation and invariants introduced here.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed sources:

- compiler/clvm/clvm_vm.h;
- compiler/clvm/clvm_vm.c;
- kernel/metal/job.h;
- kernel/metal/job.c;
- kernel/gfx/input.c;
- kernel/gfx/shader/sh_int.h;
- kernel/gfx/shader/sh_parse.c.

Reviewed symbols:

- ClvmVm;
- clvm_vm_push64;
- clvm_vm_pop64;
- job_init;
- job_submit;
- job_worker_once;
- queue_push;
- input_next_event;
- Ast;
- ShComp;
- sh_parse.

The source supports bounded array stacks, two concrete ring conventions and index-linked AST sequences. No generic ChrisOS linked-list library is inferred from these examples.
