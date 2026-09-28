---
id: resource-lifetime
lang: en
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/proc.c
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/heap.c
  - kernel/metal/kthread.c
  - kernel/metal/syscall.c
  - kernel/net/sock.c
  - kernel/lang/clvm_sys.c
  - compiler/lang_pipeline.c
  - compiler/jit/jit.c
  - kernel/gfx/gfx_slot.c
  - kernel/gfx/gfx3d.c
  - kernel/gfx/shader/sh_api.c
  - kernel/metal/job.c
symbols:
  - proc_destroy
  - proc_release_user
  - mm_free_user_space
  - mm_tlb_shootdown_range
  - mm_tlb_quarantine
  - kthread_join
  - lang_kill
  - lang_slot_release_gfx
  - clvm_sys_close_slot
  - syscall_close_owner
  - sock_close_slot
  - sock_close_proc
  - gfx_slot_free
  - gfx3d_context_destroy
  - sh_guest_drop_owner
depends_on:
  - heap-ownership
  - spinlocks
  - tlb-shootdown
related:
  - process-lifecycle
  - kernel-jobs-kthreads
  - jit-memory
  - address-spaces
---

# Resource lifetime, teardown and safe reclamation

## Scope

Allocation is only half of resource management.

A kernel object is safe to reclaim only after every actor that can still reach, execute, DMA into, translate to or otherwise use that object has stopped doing so.

ChrisOS does not currently have one universal object manager or garbage collector for kernel resources. Lifetime is expressed through subsystem-specific ownership rules and explicit destroy paths.

Examples include:

- process-owned physical pages and page tables;
- kernel-heap buffers;
- kthread stacks;
- JIT physical frames and executable mappings;
- graphics slot buffers;
- shader/program objects;
- CLVM file descriptors;
- TCP socket slots;
- input-capture ownership;
- process-owned syscall handles.

The common engineering problem is the same:

~~~text
creation -> publication -> active use -> detachment -> quiescence -> reclamation
~~~

A free operation performed before detachment or quiescence creates a use-after-free. A resource that is detached but never reclaimed becomes a leak.

![Generic resource teardown order](../../assets/diagrams/resource-lifetime-en.svg)

## Ownership versus reachability

Ownership answers which subsystem is responsible for eventually destroying a resource.

Reachability answers who can still access it right now.

Those are different questions.

A process may be the owner of a physical page while:

- its page table still maps that page;
- a CPU still caches the translation in a TLB;
- another structure still stores the physical address.

The owner is known, but reclamation is not yet safe.

Similarly, a language runtime slot may own a graphics surface while the window/task layer still refers to the slot.

Destroying the backing buffer before those references are detached would violate lifetime even though the nominal owner initiated the destruction.

## The teardown state machine

A useful generic teardown model is:

1. **Stop creation of new references.**
2. **Mark the object closing, dying or otherwise unavailable.**
3. **Detach public references and handles.**
4. **Wait for in-flight users when necessary.**
5. **Stop asynchronous producers such as CPUs, devices or callbacks.**
6. **Unmap or invalidate addressability.**
7. **Destroy child resources.**
8. **Free backing memory.**
9. **Clear ownership metadata so the slot can be reused.**

Not every current ChrisOS resource implements every explicit state.

The ordering principle still applies.

## Why locks alone are insufficient

A spinlock solves simultaneous mutation of protected metadata.

It does not automatically solve lifetime after the lock is released.

Consider:

~~~text
CPU A locks table
CPU A removes object pointer
CPU A unlocks table
CPU A frees object

CPU B had already copied the pointer before removal
CPU B dereferences freed object
~~~

The table lock can be perfectly correct while the lifetime protocol is wrong.

Solutions depend on the resource:

- reference counts;
- generation handles;
- join/wait;
- owner-specific close sweeps;
- hardware completion;
- TLB shootdown;
- quarantine;
- immutable boot lifetime.

ChrisOS currently uses several of these patterns in different places.

## Parent and child resources

Many kernel objects form ownership trees.

For example, a process owns:

- user leaf frames;
- lower-half page-table pages;
- its PML4 root;
- syscall-owned file slots;
- socket slots associated with the process.

A language runtime slot can own:

- JIT frames;
- VM/user RAM;
- graphics surfaces;
- shader/program state;
- sockets;
- CLVM file handles;
- a process object.

A correct parent destroy path must either:

- explicitly destroy each child;
- transfer ownership elsewhere;
- or prove the child is independently managed.

Simply clearing the parent slot is not enough.

## Process destruction

proc_destroy is a concrete multi-layer teardown path.

The current sequence is approximately:

~~~text
if process is current:
    switch to kernel process

release user leaf pages
free lower-half page-table hierarchy and PML4
close syscall-owned resources
close process-owned sockets
mark process slot free
~~~

The first step is critical.

A process must not free the page-table root that the BSP is still using in CR3.

If the target process is current, proc_destroy first calls proc_switch(PROC_KERNEL).

Only then can the old address-space structures be reclaimed.

## User leaf-frame ownership

proc_release_user walks the process-owned page ledger.

For each recorded page it:

1. clears the user mapping with mm_unmap_cr3 when CR3 exists;
2. returns the physical leaf frame with pmm_free;
3. clears the page-ledger entry.

Afterward it resets:

- npages;
- VM byte count;
- framebuffer page count;
- heap break.

This shows a deliberate ownership split:

~~~text
Proc.pages[] owns user leaf frames
MM page-table hierarchy owns intermediate table frames
~~~

Those two classes are destroyed by different functions.

## Page-table hierarchy destruction

mm_free_user_space frees the user-half intermediate tables and the PML4 root.

It walks only PML4 entries 0 through 255.

The upper half is shared from the kernel address space and must not be recursively freed by process teardown.

The function recursively frees page-table pages but does not free the process leaf frames.

That responsibility remains with proc_release_user.

This separation prevents accidental double-free of user data frames.

## Current user-TLB assumption

There is an important current architectural dependency.

proc_release_user clears a leaf and immediately pmm_free's the corresponding frame.

mm_unmap_cr3 invalidates locally only when the target CR3 is the currently loaded address space.

The process scheduler is currently BSP-only.

Therefore the present design relies on the fact that user address spaces are not actively running on arbitrary APs.

If native user processes are later allowed to migrate or execute concurrently on multiple CPUs, process teardown will need a broader per-address-space TLB invalidation/quiescence protocol before leaf frames can be reused.

The existing kernel-shared TLB shootdown mechanism demonstrates the required class of solution, but the current process destroy path is not yet a general SMP address-space reclamation algorithm.

## Closing process-owned handles

After page-space teardown, proc_destroy calls:

- syscall_close_owner(pid);
- sock_close_proc(pid).

These functions use owner identity to find resources that belong to the process and mark/close them.

This is an ownership-sweep pattern.

The process does not need to remember every individual socket descriptor in its Proc structure if the socket subsystem can enumerate its own table by owner.

The trade-off is that every owner-aware resource class must participate in teardown explicitly.

## Owner-indexed cleanup

ChrisOS uses owner identifiers in several subsystems.

Examples:

- socket entries have process/slot ownership;
- shader guest objects have an owner;
- graphics 3D handles validate owner plus generation;
- syscall file entries associate with a PID;
- CLVM file entries associate with a language slot.

Owner indexing is useful for bulk teardown:

~~~text
for every resource:
    if resource.owner == dying_owner:
        destroy(resource)
~~~

It is simple and robust for bounded tables.

The cost is O(N) scanning and the risk that a newly added resource class is forgotten by the parent destroy path.

## Runtime-slot teardown

lang_kill is the main teardown path for a language VM slot.

The reviewed sequence includes:

1. free JIT state if present;
2. release slot RAM;
3. release graphics state;
4. close CLVM/system-owned resources;
5. free the loaded file buffer;
6. destroy the associated process when present;
7. mark the runtime slot unused;
8. clear dying/task/name/JIT state.

This is a cross-subsystem destructor.

Its ordering matters because child subsystems can refer to slot identity while cleanup is still running.

## Why JIT memory is released early

lang_kill invokes jit_free before clearing the slot and process state.

JIT memory can be executable on CPUs and therefore has stronger reclamation requirements than an ordinary heap buffer.

jit_free:

1. removes executable mappings;
2. requests TLB shootdown;
3. only returns physical frames directly to PMM if reuse is proven safe;
4. otherwise puts them into MM quarantine.

This is a good example of lifetime being stronger than ownership.

The runtime slot owns the JIT buffer, but ownership alone is not proof that stale hardware translations no longer exist.

## Slot RAM

The language runtime tracks memory associated with the VM slot separately from JIT executable frames.

The slot teardown clears this runtime memory before the slot is made reusable.

This prevents a newly created runtime occupying the same slot from inheriting pointers to the previous program's storage.

The important invariant is:

~~~text
slot reusable -> all previous slot-owned memory references cleared
~~~

Resetting a slot identifier before child teardown would make owner-based cleanup ambiguous.

## Graphics-slot teardown

lang_slot_release_gfx finds the graphics slot and calls gfx_slot_free.

gfx_slot_free releases:

- pixel buffer;
- optional z-buffer.

It then clears pointers and the used flag and resets global z-buffer binding defaults.

This is a direct parent-child ownership pattern.

The graphics slot is not merely marked unused while its buffers remain allocated.

## Resize as replacement transaction

gfx_slot_resize and gfx_slot_resize2d illustrate replacement lifetime.

They first allocate the new buffer.

Only after allocation succeeds do they free the old buffer and publish the replacement pointers.

The principle is:

~~~text
allocate replacement
if allocation failed:
    preserve old valid object
else:
    release old
    publish new
~~~

Freeing the old buffer before proving the new allocation succeeds would turn an allocation failure into data loss.

## Graphics handles and generations

The 3D subsystem uses handles that include a generation component.

When slots are reused, generation changes.

This reduces stale-handle aliasing: an old numeric handle should not automatically become valid for a newly allocated object occupying the same table index.

Generation handles are a lightweight lifetime-defense mechanism.

They do not replace actual resource destruction, but they help detect references that outlive an object.

## GPU and CPU backing teardown

gfx3d resources can have both CPU and device backing.

For a mesh, release_mesh_dev destroys device-side buffers, while mesh_free_buf releases CPU memory.

For a texture, destruction can remove device texture/view objects and then free CPU pixels.

The general rule is:

~~~text
stop/destroy device-visible object
then release CPU backing
then mark slot dead
~~~

Hardware-backed resources often require a stricter quiescence protocol than ordinary heap objects.

The current exact device commands are subsystem-specific.

## Shader owner cleanup

clvm_sys_close_slot calls sh_guest_drop_owner(slot_id).

That function walks guest shader and program tables and destroys every object owned by the closing slot.

This is bulk owner cleanup.

It prevents a dead VM slot from leaving persistent shader/program objects in global tables.

The host test_shader code also checks owner cleanup behavior.

## File-handle teardown

CLVM file entries can hold heap buffers and dirty state.

fd_free:

1. writes dirty buffered content when needed;
2. frees the heap buffer;
3. clears buffer pointer;
4. clears used/dirty/streaming state.

clvm_sys_close_slot scans all CLVM file entries and invokes fd_free for entries belonging to the slot.

This allows abnormal VM termination to close resources even if guest code never called fclose.

That is an important kernel/runtime rule:

> process or VM exit must not depend on cooperative guest cleanup.

## Socket teardown

clvm_sys_close_slot calls sock_close_slot.

proc_destroy separately calls sock_close_proc.

sock_close_matching scans the socket table for matching owner/slot entries.

For an established connection it sends a FIN/ACK-style close before marking the slot free.

Then state becomes SK_FREE and slot ownership is cleared.

The exact TCP teardown is intentionally simplified, but the resource-table lifetime is explicit.

## Input and other slot-owned state

The slot close path also releases input capture and voxel ownership.

These resources are not heap allocations in the same sense as a byte buffer, but they still have lifetime.

A global subsystem must not continue believing that a dead slot owns an input focus/capture token.

Resource lifetime applies to logical capabilities as well as memory.

## Kthread lifetime

kthread_create allocates a private 32 KiB stack from the heap.

The job executes the kthread callback and sets done.

kthread_join waits until done becomes true.

Only after completion does it:

1. lock the slot table;
2. detach the stack pointer;
3. clear slot metadata;
4. unlock;
5. kfree the detached stack.

The wait before free is the quiescence step.

Freeing the stack while kt_run is still executing on it would be catastrophic.

## Detach before free

kthread_join also demonstrates a useful lock/lifetime pattern.

The stack pointer is detached while g_slot_lock is held.

The lock is released before kfree.

This prevents other code from finding the stack through the kthread slot while avoiding nested slot-lock -> heap-lock lifetime during free.

Conceptually:

~~~text
lock owner table
remove public reference
unlock owner table
free detached object
~~~

This pattern reduces lock-order complexity.

## Queued work and argument lifetime

job_submit stores a function pointer and a raw void * argument.

The queue does not copy or retain the pointed-to object.

Therefore the submitter must guarantee that the argument remains alive until the worker invokes the callback.

This is an implicit borrowed-reference contract.

A stack-local object or immediately freed heap object cannot safely be queued as a job argument unless completion is guaranteed before its lifetime ends.

The job system tracks inflight counts, but it is not a general reference-counting system for callback arguments.

## Dying states

A dying state is useful when teardown spans several operations.

It prevents repeated public operations from treating an object as fully alive while its children are already disappearing.

lang_kill accepts slots that are used or dying and resets dying only after cleanup.

A more formal state machine could distinguish:

~~~text
FREE -> INITIALIZING -> LIVE -> DYING -> FREE
~~~

Not every current subsystem implements this full enumeration, but the model helps avoid double teardown and partial reuse.

## Idempotence

Destroy functions vary in their tolerance of repeated calls.

Examples:

- kfree detects double free and panics;
- many slot destroy functions return when the slot is already invalid;
- jit_free returns if buf is null or phys is zero;
- proc_destroy returns when PID is invalid or unused.

An idempotent destroy API can simplify failure rollback.

A non-idempotent API can detect programming errors more aggressively.

The contract must be known per resource.

## Partial construction and rollback

Construction paths can fail after acquiring several resources.

Correct code unwinds only what it successfully acquired.

Examples in the current tree include:

- graphics allocation freeing the first buffer if the second fails;
- JIT allocation returning physical pages if virtual-range allocation fails;
- process creation calling proc_destroy if initial stack commit fails.

The general pattern is:

~~~text
acquire A
acquire B
acquire C

if C fails:
    release B
    release A
~~~

Rollback order should usually reverse dependency order.

## Executable-memory reclamation

JIT teardown demonstrates delayed reclamation.

After an executable alias is unmapped, a remote CPU may still have a cached TLB translation.

Returning the physical frames to PMM immediately can allow those frames to be allocated for unrelated data while a stale CPU can still execute them.

The safe relation is:

~~~text
unmap
  ->
invalidate every relevant CPU
  ->
prove reuse safe
  ->
free physical frame
~~~

If proof fails, ChrisOS quarantines the frame rather than reusing it.

A memory leak is safer than stale executable access.

## TLB quarantine

MM maintains a bounded quarantine of physical extents.

mm_tlb_quarantine immediately frees frames if reuse is already safe.

Otherwise it stores the physical range.

mm_tlb_reap later releases quarantined ranges when the TLB runtime reports reuse safe.

If the quarantine is full, the incoming frame is intentionally not freed.

This can leak memory, but preserves the stronger safety invariant.

That is an explicit failure policy:

~~~text
resource exhaustion > unsafe reuse
~~~

## Physical versus logical destruction

A resource can be logically destroyed before physical storage is reclaimed.

For quarantined JIT frames:

- the runtime no longer exposes the JIT object;
- its executable virtual range has been removed;
- the physical pages may still remain reserved in quarantine.

Therefore “destroyed” at the API level does not always mean “physical pages already reusable.”

Kernel diagnostics should distinguish these layers.

## Lifetime and security

Lifetime errors are security errors because use-after-free can convert stale authority into access to a new owner's data.

Relevant protections include:

- clearing ownership flags before slot reuse;
- generation-tagged handles;
- explicit owner validation;
- unmapping before physical reuse;
- not depending on guest cooperation for close;
- resetting pointers after free.

Current ChrisOS still lacks broad hardening mechanisms such as:

- generic reference counting framework;
- kernel-wide RCU/epoch reclamation;
- lockdep lifetime annotations;
- allocator poisoning;
- global object-generation infrastructure.

The current model is explicit and subsystem-specific.

## Validation strategy

Resource lifetime needs tests that exercise destruction, not only creation.

Useful evidence includes:

- repeated create/destroy cycles;
- allocation-failure rollback;
- owner cleanup after abnormal VM/process death;
- graphics resource counts returning to baseline;
- cross-CPU TLB teardown;
- no stale handles after slot reuse;
- kthread join before stack free;
- file buffers released after close;
- sockets removed after owner destruction.

The existing VirGL demo includes a resource-leak check around context destruction.

TLB protocol host tests verify that reuse remains blocked until required acknowledgement or fenced halt/flush conditions hold.

These tests target lifetime invariants directly.

## Current architectural limitations

At the reviewed revision:

- there is no single kernel-wide ownership registry;
- destroy ordering is encoded manually in each subsystem;
- owner sweeps are bounded-table scans rather than generic object graphs;
- user-process address-space reclamation assumes BSP-only native execution;
- some resources are boot-lifetime and have no runtime destroy path;
- job arguments are raw borrowed pointers;
- TLB quarantine is bounded and can intentionally leak on overflow;
- resource APIs differ in idempotence and stale-handle defenses.

These limits make documentation of each destroy path particularly important.

## Source-review checklist

When adding a new resource type, review:

1. Who allocates it?
2. Who owns it after publication?
3. Can ownership transfer?
4. Which global tables or handles can reach it?
5. Can an IRQ, AP, job or device still access it asynchronously?
6. What marks the beginning of teardown?
7. How are new references prevented?
8. What proves existing users are quiescent?
9. Are mappings or hardware bindings removed before backing memory?
10. What happens if teardown itself partially fails?
11. Is repeated destruction allowed?
12. What test proves the resource returns to baseline?

A resource without answers to these questions is not lifecycle-complete.

## Revision boundary

This chapter was reconciled against ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

The current source-backed model is not “call free when done.” It is:

~~~text
identify owner
  -> detach references
  -> stop or wait for users
  -> close/unmap child resources
  -> satisfy hardware/TLB quiescence
  -> reclaim backing storage
  -> clear owner metadata
  -> permit slot reuse
~~~

The exact operations differ by process, kthread, runtime slot, graphics resource, file, socket and JIT frame, but the lifetime invariant is shared.
