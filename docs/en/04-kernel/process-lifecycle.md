---
id: process-lifecycle
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/syscall.c
  - kernel/net/sock.c
  - kernel/metal/irq.c
  - tools/test_pmm_cycle.c
symbols:
  - proc_init
  - proc_create
  - proc_destroy
  - proc_switch
  - proc_commit
  - proc_release_user
  - proc_block
  - proc_unblock
  - proc_fault_demand
  - proc_set_vm
  - proc_sbrk
  - proc_fb_ptr
  - mm_free_user_space
depends_on:
  - virtual-memory
  - physical-memory
  - user-mode-entry
related:
  - user-copy
  - processes-syscalls
  - page-faults
---

# Process lifecycle and state

## Scope

ChrisOS process management in the reviewed revision is deliberately bounded and explicit. There are at most 32 process slots. Slot zero is the kernel. User processes own a page-table root, a bounded table of owned user pages, fixed-region virtual-memory metadata, a small state value and a short name. User process switching occurs only on the BSP.

This is not a conventional mature scheduler with arbitrary threads per process, per-CPU run queues and signal semantics. It is nevertheless a real process lifecycle: creation allocates an address space and initial stack, mapping establishes owned physical frames, page faults can commit memory lazily, blocking changes runnable state, destruction tears down frames/address space and closes resources.

## Process table

`g_proc[PROC_MAX]` is a static array with `PROC_MAX = 32`.

The internal `Proc` stores:
- `used`: slot allocation;
- `alive`: whether execution is still valid;
- `state`: FREE, READY or one of the blocking reasons;
- `cr3`: process page-table root;
- `vm_bytes`: length of the VM demand region;
- `heap_brk`: current heap break;
- `npages`: count of owned pages;
- `fb_pages`: framebuffer-region page count;
- 24-byte process name;
- up to 288 `ProcPage` ownership records.

Each `ProcPage` records virtual and physical address for a frame owned by the process.

This ownership table is central to teardown: mappings alone do not tell the kernel which physical frames it should return to PMM.

## Fixed states

The public header defines:
- `PROC_ST_FREE`;
- `PROC_ST_READY`;
- `PROC_ST_BLOCK_SOCK`;
- `PROC_ST_BLOCK_JOIN`;
- `PROC_ST_BLOCK_IRQ`.

A process is considered runnable only when its slot is valid, alive and state is READY.

The state is intentionally small. There is no separate zombie state, stop/continue state, priority or per-thread state in this structure.

## State transitions

The process-state API is intentionally small enough to express as a finite set of transitions:

| From | Operation/event | To |
|---|---|---|
| FREE | successful `proc_create` initialization | READY |
| READY | `proc_block(pid, reason)` | BLOCK_SOCK / BLOCK_JOIN / BLOCK_IRQ |
| blocked | `proc_unblock` or matching `proc_unblock_why` | READY |
| any live user state | fatal user fault | alive = 0, then teardown |
| any used user slot | `proc_destroy` | FREE |

`alive` and `state` are separate fields. `proc_runnable` requires both `alive` and READY, so recording a fault can make a process non-runnable before its slot is finally cleared by destruction. This two-field model is simple but means callers must not infer liveness from `state` alone.

## Initialization

`proc_init` resets every slot: not used, not alive, FREE, no CR3, no VM allocation, heap break reset to `PROC_HEAP_VIRT`, no pages and empty name.

Then it installs slot zero as the kernel:
- used = 1;
- alive = 1;
- state = READY;
- CR3 = `mm_kernel_cr3()`;
- name = “kernel”.

`g_current` becomes `PROC_KERNEL` and the slice flag and last-fault record are reset.

The kernel process therefore participates in the same current-PID namespace even though it does not use the user-page ownership path.

## Creating a process

`proc_create(name)` scans slots 1–31 for an unused entry.

For a candidate it calls `mm_clone_kernel_space()`. A zero return aborts creation.

The slot is then initialized as alive/READY, with its new CR3, empty owned-page table, heap break at `PROC_HEAP_VIRT` and copied name.

Creation immediately calls:

```c
proc_commit(i, PROC_STACK_VIRT)
```

If initial stack-page commitment fails, `proc_destroy(i)` unwinds the process and creation returns -1.

A successfully returned PID therefore already has an address space and at least one owned user stack page.

## Kernel mappings in a process

The name `mm_clone_kernel_space` indicates that user address spaces retain the kernel mappings needed for controlled entry/exit while obtaining an independent lower user space. Exact page-table topology belongs to the virtual-memory chapter.

The process object stores the returned CR3 rather than copying kernel virtual mappings itself.

This design means the privilege boundary is enforced by page flags, not by making kernel code completely absent from every CR3. Supervisor mappings may exist while CPL 3 is forbidden from accessing them.

## User virtual layout

Current constants are:

| Purpose | Base |
|---|---:|
| VM image/data area | `0x02000000` |
| heap | `0x04000000` |
| framebuffer buffer | `0x06000000` |
| stack | `0x07F00000` |
| library | `0x08000000` |

`PROC_PAGES = 288` bounds the number of tracked owned pages. The VM byte limit is clamped to that many pages. Heap growth is separately limited to 256 KiB.

These are concrete capacity choices, not general x86 limits.

## Mapping without and with ownership

`proc_map_user` validates the PID and lower-half address, then invokes `mm_map_cr3` with `MM_USER` added to supplied flags.

`proc_map_owned` additionally:
- page-aligns the virtual address;
- rejects duplicates;
- rejects ownership-table overflow;
- maps the frame;
- records virtual/physical pair.

On failure to record/map, the caller remains responsible for freeing a frame that was not transferred into process ownership.

The distinction between “map” and “map + own” prevents ambiguous teardown responsibility.

## Committing a page

`proc_commit` is the standard owned-page allocation path.

It aligns the address and treats an already-owned page as success. It checks the 288-entry limit, allocates a physical frame with `pmm_alloc` and zero-fills the entire 4 KiB page through the physical-to-virtual mapping.

It maps the frame as Present + Write + User. If mapping fails, the frame is returned to PMM.

Then it appends the ownership record. If the process is currently selected, the function flushes TLB.

Zero-fill is both a correctness and security property: a newly exposed user page must not reveal data left by a previous frame owner.

## Demand regions

`proc_set_vm(pid, bytes)` clamps VM size to the process-page capacity, stores the length and eagerly commits the first VM page. The rest can arrive on demand.

`proc_fault_demand` page-aligns CR2 and recognizes:
- VM range from `PROC_VM_VIRT` to `PROC_VM_VIRT + vm_bytes`;
- four stack pages starting at `PROC_STACK_VIRT`;
- heap pages below current `heap_brk`;
- framebuffer pages within configured count.

If CR2 lies in one of these regions, it calls `proc_commit`. Otherwise it reports that the fault is not recoverable by demand allocation.

This turns region metadata into a page-fault policy.

## Heap growth

`proc_sbrk(pid, inc)` returns the old break and advances the process break if the result stays within 256 KiB above `PROC_HEAP_VIRT`.

It does not eagerly allocate every page crossed. Later access faults and `proc_fault_demand` commits pages below the new break.

The current function also does not implement negative increments or heap shrink. Its unsigned interface is grow-only.

## Framebuffer region

`proc_fb_ptr(pid, pages)` clamps requested pages to at most 16, stores the count and eagerly commits each framebuffer-region page.

It returns the fixed virtual base `PROC_FB_VIRT`.

This is a process-owned software buffer mapping, not direct ownership of a physical GPU framebuffer. The graphics/security implications should be distinguished from MMIO mapping.

## Switching

`proc_switch(pid)` first enforces:

```c
if (smp_current_cpu() != 0u)
    panic("process switch off BSP");
```

For a valid used PID it reads the process CR3, updates `g_current` and calls `mm_switch`.

The invariant is explicit: user process scheduler state is global and is not safe to mutate from APs.

This rule prevents simultaneous CPUs from treating one global `g_current` as their independent current process.

## Timer slice state

The PIT handler eventually calls `proc_on_tick`, which sets `g_slice = 1`.

`proc_slice_due` reads this flag; `proc_slice_ack` clears it.

This is scheduling metadata, not the complete process switch. The lifecycle code does not contain a fully preemptive multi-process context-switch state machine.

## Blocking

`proc_block(pid, why)` replaces process state with a blocking reason. `proc_unblock(pid)` restores READY. `proc_unblock_why(why)` scans every user process and makes all processes blocked for that reason READY.

The API is intentionally coarse. It does not maintain per-object waiter queues in the process table itself.

Subsystems such as sockets or join semantics can use these states as a global scheduling signal.

## Fault records and liveness

`proc_record_fault` stores one global `ProcFault` containing valid flag, pid, tid, CR2 and RIP. If the PID is valid it sets `alive = 0` and logs identifying information.

`proc_last_fault` exposes the record.

The record is “last fault” diagnostic state, not a per-process history. A later fault overwrites it.

User-fault handling then destroys the process and arranges return to kernel code.

## Destruction

`proc_destroy(pid)` rejects kernel PID and invalid slots.

If the process being destroyed is current, it first switches to `PROC_KERNEL`. This is essential: freeing the active user page tables while CR3 still points at them would destroy the address-space context executing teardown.

It then:
1. releases every owned user frame;
2. frees the user page-table structure if it is distinct from kernel CR3;
3. closes syscall-owned file descriptors for the PID;
4. closes sockets owned by the process;
5. marks the slot FREE/not alive and clears CR3.

This is ordered teardown: leave the address space before dismantling it, release mappings/frames, release subsystem resources, then make the slot reusable.

## Releasing user pages

`proc_release_user` iterates ownership records. For each physical frame:
- unmaps the virtual address from process CR3 if a CR3 remains;
- returns physical frame to PMM;
- clears record fields.

After the loop it resets page count, VM bytes, framebuffer page count and heap break.

The ownership table ensures each recorded frame is freed once. Duplicate virtual addresses are rejected during owned mapping, reducing double-ownership risk.

## Layered teardown: frames versus page tables

Process teardown separates two ownership classes that are easy to conflate.

`proc_release_user` owns leaf data frames recorded in `ProcPage[]`. It unmaps each recorded virtual address and returns the associated physical frame to PMM. After those leaf frames are gone, `mm_free_user_space` walks only the lower 256 PML4 entries and recursively frees user-half intermediate page-table pages plus the process PML4 itself. Its contract explicitly leaves leaf frames to the process ownership list.

The order prevents two classes of bug: freeing a leaf frame twice through both VM and process code, or freeing page-table structures while they are still needed to locate/unmap owned leaves. Kernel-half mappings are not recursively freed as part of a user process because they are shared architectural context, not process-owned leaves.

## File and socket cleanup

`syscall_close_owner(pid)` scans the small syscall file table and invalidates descriptors belonging to the process.

`sock_close_proc(pid)` performs analogous network-resource cleanup in the socket layer.

This demonstrates that process destruction is a cross-subsystem operation. Adding future resource classes requires either extending teardown or introducing a more general owned-handle mechanism.

## Current-process destruction

The initial switch to kernel PID before release also changes CR3 through the normal `proc_switch` path.

Because only the BSP is allowed to switch processes, destruction of the current user process is expected on BSP. A future concurrent architecture must guarantee that no other CPU can still execute in the address space before pages/page tables are freed.

This requirement connects process teardown directly to TLB shootdown and task migration.

## Capacity coupling and partial-failure semantics

The 288-entry ownership table is shared by all process-owned mappings. VM pages, stack growth, heap pages and the software framebuffer all consume the same `ProcPage[]` capacity. Consequently, each region's nominal size is not an independent reservation.

For example, `proc_set_vm` can advertise up to `PROC_PAGES * 4096` bytes, but the process already owns its initial stack page. A VM request at the nominal maximum therefore cannot materialize every VM page through `proc_commit` without exhausting the shared ownership table. Heap and framebuffer commitments further reduce the available count.

Failure can also leave useful metadata in place. `proc_set_vm` stores `vm_bytes` before committing the first VM page; if that commit fails, the function returns zero while the declared VM range remains recorded. `proc_fb_ptr` stores `fb_pages` before committing the pages, so a mid-loop allocation failure can leave a partially materialized framebuffer region whose already-owned pages are still correctly reclaimed by later teardown.

These are concrete current semantics. Callers should treat a returned failure as failure even though the process object may retain region metadata used by later demand-fault logic.

`proc_sbrk` is grow-only and checks `old + inc` against the 256 KiB ceiling, but the current expression does not first reject unsigned addition overflow. With an adversarially large increment, wraparound is therefore an implementation edge case that should be covered by validation before this interface is treated as hardened.

## Capacity and failure

Creation fails if:
- no free process slot exists;
- kernel-space cloning fails;
- initial stack commit fails.

Commit fails if:
- PID invalid;
- ownership table full;
- PMM allocation fails;
- page mapping fails.

Framebuffer setup can partially commit pages before a later failure; callers need to treat the process-owned page table as the source of teardown truth.

No overcommit policy or swap exists in the reviewed path.

## Security properties

User frames are zeroed before exposure. Mappings receive `MM_USER` only through the user mapping path. Virtual addresses at or above the lower canonical limit are rejected in `proc_map_user`.

Destroying a process closes its user-visible file/socket ownership, limiting handle leakage into a reused slot.

The fixed PID slot is not generation-tagged. If external code stores a PID after destruction and later the slot is reused, stale PID references could refer to a different process unless callers enforce lifetime. A mature handle model commonly pairs index with generation or stronger references.

## Performance characteristics

Process lookup and creation scan a fixed 32-entry array: bounded O(32). Owned-page lookup is linear in at most 288 records. Destruction similarly walks the owned list.

For current small limits this favors simplicity over sophisticated VM trees. Scaling to thousands of mappings/processes would require different data structures.

Demand paging reduces eager allocation but adds first-touch faults.

## Existing executable evidence and gaps

`tools/test_pmm_cycle.c` verifies the lower-layer allocator's accounting across 1,000 allocations and frees: free-page count falls by exactly 1,000 and returns to its original value after the cycle. That is relevant evidence for the PMM primitive used by `proc_commit` and `proc_release_user`.

It is not a lifecycle test. The host test does not create real `Proc` objects, clone CR3 roots, exercise `proc_destroy`, verify descriptor/socket cleanup or prove that process-owned frames and user page-table pages are each released exactly once. The lifecycle chapter therefore distinguishes lower-layer allocator evidence from the still-needed process-level create/destroy gate.

## Validation

Lifecycle tests should verify:
- all 31 user slots and exhaustion;
- clone failure/stack allocation unwind;
- duplicate owned mapping rejection;
- zero-filled new pages;
- VM/stack/heap/framebuffer demand boundaries;
- heap maximum;
- switch-on-AP panic invariant;
- block/unblock transitions;
- destruction of current process switches to kernel first;
- every owned frame returns exactly once;
- file/socket ownership closes;
- PID slot can be reused only after complete cleanup.

A leak test comparing PMM free state before/after repeated create/destroy cycles is especially valuable.

## Current limitations

One process-level execution context is represented per PID; no user threads are modeled here. Current process and scheduling state are global/BSP-only. Limits are static. Heap only grows. Fault history is one global record. Resource teardown is explicitly wired to known subsystems.

These limits should remain visible instead of being obscured by generic language such as “full process management”.

## Revision reconciliation

The lifecycle implementation sources described here are unchanged between the former reviewed revision and `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Repository changes in between were documentation/project-maintenance changes rather than modifications to the process, MM, PMM or teardown code. The page is therefore reconciled to the newer source revision without introducing new runtime claims.

## Source map

`kernel/metal/proc.c`/`proc.h` define process state and lifecycle. `mm.c`/`mm.h` provide CR3/mapping operations. `pmm.c`/`pmm.h` own physical frames. `syscall.c` and `kernel/net/sock.c` participate in teardown. The Source Atlas publishes each source in full at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
