---
id: clvm-memory
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/clvm/clvm.h
  - compiler/chrisc/chrisc.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - kernel/lang/clvm_sys.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/pmm.h
  - kernel/metal/irq.c
  - tools/test_load64_zero.c
  - tools/test_store64_step.c
  - tools/test_store64_copy.c
  - tools/test_doom_jit_smoke.c
  - tools/test_doom_strinit.c
symbols:
  - clvm_vm_init
  - clvm_vm_set_memory
  - mem_ok
  - clvm_guest_malloc
  - clvm_guest_free
  - clvm_guest_realloc
  - clvm_guest_setjmp
  - clvm_guest_longjmp
  - lang_attach_slot_ram
  - lang_free_slot_ram
  - proc_set_vm
  - proc_vm_ptr
  - proc_commit
  - proc_fault_demand
  - vm_bytes
  - vm_cstr
  - vm_copy_in
  - vm_copy_out
  - clvm_threads_tick
depends_on:
  - chrisc-clvm
  - clvm-bytecode
related:
  - clvm-syscalls
  - clvm-interpreter
  - calling-conventions
  - gc-libraries
  - virtual-memory
  - process-lifecycle
---

# CLVM memory, allocation and isolation

## Scope

CLVM presents a flat guest-memory region to bytecode while ChrisOS may back that region in different ways.

At the VM level, an address is an integer offset into:

    vm->memory[0 .. vm->mem_size)

At the operating-system level, vm->memory may refer either to a kernel-heap allocation or to a fixed virtual range mapped into a ChrisOS process address space.

Those two layers must be kept separate.

The CLVM guest does not receive arbitrary host pointers for ordinary loads and stores. LOAD, LOADB, LOAD64, FLOAD and the corresponding stores interpret stack values as guest offsets and validate them against mem_size before dereferencing memory.

The runtime, however, contains additional helper and syscall paths with their own validation rules. Isolation therefore depends on all of those paths, not only on the core interpreter.

![CLVM memory layers](../../assets/diagrams/clvm-memory-en.svg)

## Address domains

Several address domains coexist in the CLVM runtime.

| Domain | Representation | Meaning |
|---|---|---|
| bytecode PC | u32 | offset inside the CLV code payload |
| guest data pointer | integer VM value | offset from vm->memory |
| vm->memory | host/kernel C pointer | base of the guest data region |
| process VM virtual base | 0x02000000 | current ChrisOS process mapping used by process-backed CLVM RAM |
| kernel heap pointer | native pointer | fallback backing allocation and kernel-owned objects |
| JIT native address | native executable address | generated host code, not a guest pointer |

A guest pointer with value 4096 normally means “byte 4096 inside CLVM guest RAM.”

It does not mean host virtual address 0x1000.

The interpreter converts the offset into a host-accessible address only after validating the range:

    host_address = vm->memory + guest_offset

This distinction is the central memory-safety invariant of the VM.

## ClvmVm memory state

ClvmVm stores:

    uint8_t *memory
    uint64_t mem_size
    uint8_t mem_owned
    uint64_t heap_off

memory is the backing base.

mem_size is the logical guest-address limit.

mem_owned indicates whether the core VM allocated the current backing and is responsible for releasing it when a different backing is installed.

heap_off is the current bump-allocation cursor.

The operand stack, call stack, IL local/argument arrays and TLS are fields of ClvmVm itself; they are not stored inside the guest data region.

## Default initialization

clvm_vm_init starts with CLVM_MEMORY_SIZE bytes.

At the documented revision:

    CLVM_MEMORY_SIZE = 1 MiB

Allocation depends on the build target.

In the freestanding ChrisOS kernel, the VM uses kmalloc/kfree.

In a hosted build it uses calloc/free.

The RISC-V build uses a static two-megabyte pool with aligned bump allocation.

When allocation succeeds, clvm_vm_init zeroes the one-megabyte region, sets mem_owned, records mem_size and chooses an initial heap_off.

This initial buffer is often temporary in the desktop pipeline because lang_attach_slot_ram can replace it with process-backed or separately allocated slot RAM.

## Replacing the backing store

clvm_vm_set_memory installs a new memory base and size.

If the VM currently owns a different backing, it releases the old buffer first.

It then clears mem_owned because the caller now owns the supplied memory.

This ownership transfer is significant.

After clvm_vm_set_memory, generic VM teardown must not blindly free vm->memory. The LangSlot or process that supplied the backing is responsible for its lifetime.

The function also recomputes heap_off from the new size.

## Heap-start heuristic

The current guest allocator does not receive the final end address of ChrisC static data.

Instead, the VM selects a heap start from memory size:

| Guest RAM size | heap_off |
|---|---:|
| at least 16 MiB | 1 MiB |
| more than 128 KiB and below 16 MiB | 64 KiB |
| 128 KiB or less | half of memory |

The source comment explains the motivation: large Doom-sized programs place globals and strings well above 64 KiB, so the allocator should begin farther away from low static data.

This is a heuristic partition, not a linker-defined segment boundary.

There is no current field in the CLV header saying “static data ends at offset X.”

That means correctness depends on the compiler's static-memory footprint remaining below the selected heap start.

## ChrisC static-memory layout

ChrisC assigns many source objects fixed guest offsets during compilation.

The compiler starts mem_next at zero.

As declarations are created, their storage is assigned from mem_next and the cursor advances according to size and alignment.

Later, chrisc_emit places the string pool after the accumulated static data, then reserves the shared ordinary-call argument area and the varargs area.

Conceptually:

    0
    +---------------------------+
    | globals / fixed variables |
    +---------------------------+
    | arrays / structs          |
    +---------------------------+
    | string pool               |
    +---------------------------+
    | icall argument scratch    |
    +---------------------------+
    | varargs scratch           |
    +---------------------------+
    | unreserved gap            |
    +---------------------------+
    | guest bump heap           |
    +---------------------------+
    | remaining RAM             |
    +---------------------------+
    mem_size

This diagram is conceptual. The current VM does not store explicit segment descriptors for those regions.

Several ChrisC paths check growth against CLVM_MEMORY_SIZE, especially aggregate and string allocations, but the heap cursor is still chosen independently by the runtime.

A sufficiently large static footprint can therefore approach or exceed the heuristic heap start.

## Core bounds-check invariant

The core interpreter uses mem_ok for ordinary bytecode memory operations.

The important form is:

    if memory is null -> reject
    if address < 0 -> reject
    if address > mem_size -> reject
    if length > mem_size - address -> reject
    otherwise -> valid

The subtraction form avoids an address+length overflow during validation.

The valid byte interval is:

    address <= x < address + length
    and
    address + length <= mem_size

LOADB/STOREB request one byte.

LOAD/FLOAD and STORE/FSTORE request four bytes.

LOAD64/STORE64 request eight bytes.

LDFLD/STFLD validate the object address plus field offset for an eight-byte transfer.

An invalid ordinary memory operation transitions the VM to CLVM_FAULT_BAD_ADDRESS.

## Logical bounds versus physical residency

For process-backed memory, mem_size describes the logical CLVM range, but not every page is necessarily resident.

proc_set_vm records the logical vm_bytes range and commits only its first page.

When execution later touches a valid but uncommitted page, the x86 page-fault path calls proc_fault_demand.

If the fault address lies inside:

    PROC_VM_VIRT <= address < PROC_VM_VIRT + vm_bytes

proc_fault_demand calls proc_commit for that page.

proc_commit obtains a physical page from the PMM, zeroes it, maps it writable into the process page table and records ownership.

The logical CLVM bounds check and the CPU demand-paging mechanism therefore solve different problems:

- CLVM bounds checks decide whether the guest is allowed to address an offset;
- process paging decides whether a physical page already exists for an allowed virtual location.

## Fixed process virtual base

proc_vm_ptr currently returns:

    PROC_VM_VIRT = 0x02000000

for every process ID.

The pointer value is intentionally the same virtual address in different process page tables.

It is meaningful only while the corresponding process address space is active.

lang_tick enforces this operational requirement by switching to the slot's process before running either clvm_step or the JIT function, then switching back to PROC_KERNEL afterward.

CLVM child threads similarly record the process in which they were created, and clvm_threads_tick switches to that process before stepping the child VM.

Kernel code that accesses process-backed vm->memory outside the execution loop must perform the same context discipline. The hot-reload checkpoint restoration path explicitly switches into the process before copying bytes.

## Process-backed slot RAM

The normal desktop launch creates a process with proc_create and then calls lang_attach_slot_ram.

For a valid process, the requested guest RAM is:

    max(image.mem_hint, CLVM_MEMORY_SIZE)

proc_set_vm may reduce that request.

The slot records:

    heap_ram
    heap_ram_sz
    user_ram = 1

and installs the process virtual pointer through clvm_vm_set_memory.

Only the first page is explicitly zeroed during attachment. Later demand-committed pages are independently zeroed by proc_commit.

The name heap_ram is historical/operational; in the process-backed case it points at the process VM virtual range rather than a kernel-heap object.

## Current process-memory ceiling

The process implementation uses:

    PROC_PAGES = 288
    PMM_PAGE   = 4096 bytes

proc_set_vm caps the logical requested VM range to:

    288 * 4096 = 1,179,648 bytes

which is about 1.125 MiB.

This is an important current limitation.

The CLV v2 format can carry a much larger memory hint, and the compiler pipeline currently writes a 32 MiB hint for sufficiently large generated programs.

The process-backed path cannot honor a 32 MiB hint at this revision because proc_set_vm clamps it to the process-page accounting ceiling.

The same ProcPage array also tracks other process-owned mappings such as the initially committed user stack, so the number of VM pages that can become resident can be lower than the theoretical 288-page range before the tracking table saturates.

The heap-backed fallback does not have this particular PROC_PAGES limit.

## Kernel-heap fallback

If proc_create fails and the slot has no process, lang_attach_slot_ram uses kernel heap memory.

It first queries heap_free_bytes and attempts to preserve:

    CLVM_HEAP_RESERVE = 64 MiB

for the rest of the kernel.

The requested guest memory is again at least one MiB and may use the CLV memory hint.

If the request exceeds the remaining capacity and that capacity is at least one MiB, the request is reduced to the available cap.

The resulting allocation is zeroed.

If the VM already had initial memory, the runtime copies as many existing bytes as fit into the replacement buffer before installing it.

In this mode, heap_ram is a real kmalloc allocation and lang_free_slot_ram releases it with kfree.

## Ownership at teardown

Process-backed and heap-backed RAM use different owners.

When user_ram is set, lang_free_slot_ram only clears the LangSlot pointers and flag. It does not free the pages.

proc_destroy later calls proc_release_user, which unmaps and frees the physical pages recorded by the process.

When user_ram is clear, lang_free_slot_ram frees heap_ram directly.

This division prevents normal slot teardown from both kfree-ing process virtual memory and later freeing the same PMM pages through process teardown.

The owner must remain unambiguous for every replacement and reload path.

## Hot reload

lang_hot_reload reinitializes ClvmVm with the new image and reattaches the slot RAM.

It can restore up to 256 bytes of explicitly saved checkpoint data if the checkpoint range fits inside the new mem_size.

For process-backed RAM, checkpoint restoration switches into the process before dereferencing vm->memory.

Hot reload does not preserve the entire guest address space as a semantic snapshot. It rebuilds VM execution state and restores only the selected checkpoint bytes.

The ownership path deserves continued regression coverage because clvm_vm_init can temporarily create an owned one-megabyte buffer before the slot backing is reinstalled.

## Guest malloc representation

clvm_guest_malloc implements a bump allocator.

For a request n, it computes:

    need = align_up(n + 8, 8)

The first eight bytes of the allocation store need.

The pointer returned to the guest is:

    p + 8

where p is the previous heap_off.

Then:

    heap_off = p + need

The layout is therefore:

    p
    +--------------------+
    | u64 allocation span|
    +--------------------+  <- returned pointer
    | payload            |
    | ...                |
    +--------------------+
    aligned end

The allocator rejects zero-size requests and requests above 2^40 bytes.

It also requires the entire new span to fit inside mem_size.

Allocation is O(1).

## Guest free

clvm_guest_free is currently a no-op that returns success.

It does not:

- validate allocation provenance;
- add a block to a free list;
- coalesce space;
- move heap_off backward.

As a result, the guest heap has monotonic high-water growth for the lifetime of a VM backing.

A program can call free successfully yet receive no reusable capacity from that operation.

This behavior must be understood when porting software that expects sustained malloc/free reuse.

## Guest realloc

clvm_guest_realloc always allocates a new block first.

If the old pointer is nonzero, at least eight, and below mem_size, it reads the eight-byte header immediately before the pointer.

It subtracts the header size, limits the copy count to the new requested size and copies bytes into the new allocation.

This gives O(n) copy cost.

However, the current implementation does not prove that the supplied old pointer is the start of an allocation created by clvm_guest_malloc.

It also does not clamp the derived old payload length against:

    mem_size - old_pointer

before copying.

A guest can therefore provide an in-range but non-provenance pointer whose preceding bytes are interpreted as an allocation header.

This is a real validation gap in the current memory boundary and should be fixed before the guest allocator is treated as robust against adversarial inputs.

The normal ChrisC malloc/realloc path is expected to pass allocator-produced pointers, but the syscall boundary itself currently relies on that behavioral contract.

## setjmp memory format

clvm_guest_setjmp serializes control state into guest memory.

The current layout begins with:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | bytecode PC |
| 4 | 4 | operand stack depth |
| 8 | 4 | call stack depth |
| 12 | 4 | marker/current format value |
| 16 | sp * 8 | operand stack entries |
| next | csp * 4 | return PCs |

This makes nonlocal control state explicit and portable within the VM representation.

The snapshot does not include arbitrary kernel resources, mutex ownership or file state.

## setjmp/longjmp range-validation gap

The current setjmp preflight checks:

    addr + 16 + sp*8 + 8 <= mem_size

but the actual serialization writes csp*4 bytes for the call stack, not a fixed eight bytes.

Therefore a sufficiently deep call stack with a buffer near the end of guest RAM can pass the current preflight and still write beyond the logical guest range.

clvm_guest_longjmp checks that the first 16 bytes fit, reads sp and csp, and validates those counts against CLVM_STACK_MAX and CLVM_CALL_MAX.

It does not then preflight the complete:

    16 + sp*8 + csp*4

serialized range before reading it.

These are concrete current isolation gaps.

They should be corrected before setjmp/longjmp are described as fully memory-safe for arbitrary guest-provided buffer addresses.

## Syscall pointer validation

Kernel-side CLVM syscalls cannot trust guest integers as C pointers.

clvm_sys.c therefore contains several copying and validation helpers.

vm_bytes validates a positive buffer length using the overflow-safe form:

    n <= mem_size - address

vm_copy_in validates the complete guest source range before copying to a kernel buffer.

vm_copy_out validates the complete guest destination range before writing from a kernel buffer.

vm_cstr walks one byte at a time and succeeds only when it encounters a NUL before either the supplied capacity or mem_size boundary.

These helpers establish an important syscall rule:

    validate guest offset and complete extent before creating a host pointer

Not every helper in the file has exactly the same string-truncation policy, so each syscall remains responsible for using the appropriate validated helper.

The syscall ABI chapter enumerates those call-specific contracts.

## Core memory access is segmentless

Within the logical [0, mem_size) data range, CLVM does not currently enforce per-segment permissions.

There is no guest-memory page attribute saying:

- read-only string pool;
- read-only globals;
- heap only;
- stack only;
- execute-only region.

Ordinary STORE instructions can write any in-range guest-data offset.

The bytecode code array is separate from vm->memory, so ordinary STORE does not directly rewrite the loaded CLV code payload through a guest data offset.

The data address space itself is nevertheless flat and read/write.

This is simpler than a protected segmented VM but provides less intra-VM fault containment.

## Threads share guest RAM

CLVM child threads are separate ClvmVm structures.

The child receives:

    code
    code_size
    memory
    mem_size
    sys
    sys_user
    process identity

from the parent.

Therefore child and parent deliberately share the same guest-memory bytes.

They do not share operand stacks, call stacks or TLS arrays because those are fields inside each ClvmVm.

The memory model is thus thread-like rather than process-like:

    shared data address space
    + independent execution stacks/state

Concurrent access to ordinary guest memory requires synchronization.

The mutex/condition syscalls use guest addresses as synchronization object locations and can block/wake child VMs.

## Child allocator-state gap

The child ClvmVm is first zeroed.

The thread-creation path then copies memory and execution-related pointers but does not copy or initialize heap_off.

Consequently the child's heap_off remains zero.

If the child invokes the ordinary guest malloc syscall, clvm_guest_malloc begins allocation at offset zero in the same memory shared with the parent.

That can overwrite globals/static data and violate the parent allocator's state.

This is a concrete current concurrency bug/limitation.

A correct shared-heap design needs either:

- one allocator cursor/state shared by all VMs in the process;
- synchronization around a shared allocator;
- or per-thread heaps with disjoint assigned regions.

The current code implements none of those three for clvm_guest_malloc.

## TLS versus guest memory

Each ClvmVm owns:

    int64_t tls[16]

This array is not part of shared guest memory.

A newly zeroed child therefore starts with independent zeroed TLS entries.

This provides a small thread-local state domain even though the main guest-data region is shared.

It is a CLVM runtime facility, not an ELF TLS implementation.

## Process paging and CLVM faults

Two fault classes can occur around memory.

A guest offset rejected by mem_ok produces:

    CLVM_FAULT_BAD_ADDRESS

inside VM state.

A logically valid process-backed address whose page is not resident can cause hardware page fault vector 14.

The interrupt path first asks proc_fault_demand to satisfy a demand fault.

If the address is within an allowed process region and a page can be committed, execution can resume.

If it is not a recognized demand range or allocation fails, the fault proceeds through the normal process/kernel fault handling path.

This distinction is important for diagnostics: not every host page fault implies a bad CLVM guest offset.

## JIT memory semantics

The JIT executes native instructions but is required to preserve the same logical guest bounds as the interpreter.

Its generated paths use ClvmVm fields for memory base, size and fault state and route unsupported/complex behavior through helpers.

The memory safety contract is therefore defined in terms of VM-visible behavior, not in terms of whether execution happens in the switch-based interpreter or generated native code.

Tests that compare interpreter and JIT paths are especially important for LOAD/STORE edge cases because an omitted JIT bound check would bypass the protection implemented in mem_ok.

## Memory hints are advisory

CLV v2 carries mem_hint.

The compiler pipeline uses a 32 MiB hint for sufficiently large generated bytecode images.

The hint is not a guarantee that the runtime will supply that exact amount.

Process policy, PROC_PAGES limits, heap availability and allocation failure can reduce or reject the request.

Software should therefore treat the effective vm->mem_size as runtime capacity, not assume the image hint was fully honored.

There is currently no guest opcode that asks the core VM directly for mem_size as part of a standardized portable memory-query ABI; application behavior depends on higher-level runtime contracts.

## Managed GC memory is a separate domain

The CLVM syscall table also exposes gc_alloc.

At the current revision, that path calls the kernel/compiler GC allocator and pushes the resulting native pointer value as an int64_t.

That value is not produced by clvm_guest_malloc and is not a normal offset into vm->memory.

It therefore belongs to a different managed/native address domain.

Ordinary CLVM LOAD/STORE instructions apply guest-offset bounds and should not be assumed to dereference such a native GC pointer.

This mixed pointer model is one reason the managed library/GC layer must remain explicitly separated from the ordinary CLVM guest heap until a unified object-reference ABI exists.

## Performance characteristics

Core bounds checks are O(1).

LOAD/STORE operations transfer at most eight bytes in the current instruction set.

Demand paging defers physical allocation, reducing initial resident memory, but first touch incurs a page fault plus PMM allocation, zeroing and page-table update.

clvm_guest_malloc is O(1).

clvm_guest_free is O(1) because it does no reclamation.

clvm_guest_realloc is O(k), where k is the number of bytes copied.

Process page ownership lookup in proc_commit uses the process page array and is linear in the number of already tracked pages.

This is bounded by PROC_PAGES, so the search is bounded but not asymptotically constant.

## Cache and locality considerations

The guest address space is contiguous logically, which gives ChrisC arrays and structures conventional spatial locality.

Heap bump allocation also places successive allocations near each other.

Process-backed physical pages need not be physically contiguous; virtual contiguity hides that distinction from CLVM.

The separate operand and call stacks live inside ClvmVm and remain compact fixed arrays, typically giving good locality for interpreter state.

Child VMs share data pages, so concurrent writes to the same guest locations can introduce normal cache-coherence traffic on SMP systems even though the virtual-machine abstraction itself is high level.

## Failure modes

Important failure modes include:

| Failure | Result |
|---|---|
| initial one-megabyte VM allocation fails | memory = null, mem_size = 0 |
| slot backing allocation fails | application launch fails |
| guest LOAD/STORE out of range | CLVM_FAULT_BAD_ADDRESS |
| guest malloc exceeds remaining region | returns failure/zero through syscall |
| process demand page cannot be committed | page fault not resolved |
| process page tracking fills | further proc_commit fails |
| free called | succeeds but reclaims nothing |
| invalid realloc provenance | currently insufficiently validated |
| setjmp/longjmp near end of memory | current total-range checks are incomplete |
| child thread malloc | current child heap_off state is unsafe |

These failure modes are not equivalent and should be diagnosed at the layer where they originate.

## Security and isolation model

The implemented isolation model is layered:

1. bytecode accesses use guest offsets rather than arbitrary direct host pointers;
2. core memory instructions enforce logical mem_size bounds;
3. process-backed execution uses separate process page tables;
4. uncommitted valid pages are demand allocated;
5. syscalls are expected to validate guest ranges before copying;
6. privileged hardware syscalls have separate capability checks;
7. slot/process teardown owns and releases backing resources.

This is meaningful isolation, but it is not yet a formally verified sandbox.

The realloc and setjmp/longjmp gaps described above show why every alternate memory path matters.

The child allocator-state bug also means shared-memory concurrency can corrupt the guest address space without violating the outer mem_size bound.

Security claims should therefore remain specific: ordinary interpreter memory operations are range checked; the complete CLVM runtime still has known memory-validation and ownership gaps.

## Validation evidence

tools/test_load64_zero.c installs a 32 MiB backing and exercises 64-bit load behavior through the JIT path.

tools/test_store64_step.c and tools/test_store64_copy.c exercise 64-bit writes and copy-sensitive behavior with a larger guest-memory region.

tools/test_doom_jit_smoke.c and related Doom diagnostic tests grow VM memory to 32 MiB in hosted test configurations and exercise large-program execution.

tools/test_doom_strinit.c reports heap_off and runs initialization using the enlarged backing, providing evidence for the one-megabyte heap-start policy used with large memory.

The broader ChrisC and JIT suites exercise many generated guest loads/stores.

The source also contains explicit bounds checks that are deterministic enough to audit.

At this revision, dedicated adversarial regression tests for invalid realloc provenance, near-end setjmp buffers and child-thread malloc state are not evident in the inspected test set. Those cases should be added.

## Current limitations

At the documented revision:

- guest memory is one flat read/write data region;
- heap/static separation is heuristic rather than derived from an explicit final static-data boundary;
- the process-backed VM request is capped by PROC_PAGES to about 1.125 MiB at current constants;
- large 32 MiB CLV memory hints are therefore not honored by the normal process-backed path;
- the process page tracking table is shared with other owned user mappings and can saturate;
- guest free does not reclaim memory;
- guest realloc does not validate allocation provenance or clamp old copy length to the remaining guest range;
- setjmp does not preflight the complete call-stack serialization size;
- longjmp does not preflight the complete serialized state before restoring it;
- child CLVM VMs share memory but do not inherit/share heap_off;
- the guest allocator is not synchronized for multi-threaded use;
- per-region read/write permissions do not exist inside vm->memory;
- native GC pointers and guest offsets currently coexist as different pointer domains;
- memory hints are advisory rather than guaranteed capacity;
- fallback and hot-reload ownership paths remain sensitive to correct mem_owned/user_ram coordination.

## Roadmap boundary

A stronger CLVM memory architecture could introduce:

- an explicit image/static-data-end field used to initialize the heap safely;
- a reclaiming allocator with validated block metadata;
- allocator provenance/canaries or a compact allocation table;
- one synchronized heap state shared by all CLVM threads;
- region descriptors with read/write permissions;
- guard pages around guest-memory mappings;
- larger process page accounting or a dynamic page-owner structure;
- a runtime query for effective memory size;
- complete setjmp/longjmp range preflight;
- a bytecode verifier that reasons about pointer-producing operations;
- a unified managed object-reference representation that never exposes raw kernel pointers.

These are future changes until corresponding source and tests exist.

## Source map and revision

Core VM memory state, bounds checking, heap allocation and setjmp/longjmp are implemented in compiler/clvm/clvm_vm.c and declared in compiler/clvm/clvm_vm.h.

ChrisC static guest-address assignment, string placement and call scratch regions are implemented in compiler/chrisc/chrisc.c.

Slot memory selection, process-context switching, fallback backing, hot reload and teardown are implemented in compiler/lang_pipeline.c.

Syscall-side guest buffer validation and CLVM thread creation are implemented in kernel/lang/clvm_sys.c.

Process virtual-memory mapping and demand commitment are implemented in kernel/metal/proc.c, with page-fault dispatch in kernel/metal/irq.c.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
