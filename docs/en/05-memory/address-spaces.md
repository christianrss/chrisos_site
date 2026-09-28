---
id: address-spaces
lang: en
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/elf.c
  - kernel/metal/syscall.c
  - kernel/metal/user_enter.c
  - kernel/tools/shell.c
  - compiler/lang_pipeline.c
symbols:
  - proc_init
  - proc_create
  - proc_switch
  - proc_map_user
  - proc_map_owned
  - proc_commit
  - proc_set_vm
  - proc_sbrk
  - proc_fb_ptr
  - proc_release_user
  - proc_destroy
  - mm_clone_kernel_space
  - mm_free_user_space
  - elf_load
  - elf_map_segment
  - syscall_set_user_map
  - enter_user
depends_on:
  - virtual-memory
  - page-table-layout
  - page-faults
related:
  - user-mode-entry
  - processes-syscalls
  - process-lifecycle
  - user-copy
  - tlb
---

# Process address spaces and virtual-memory layout

## Scope

An address space is the translation context that defines which virtual addresses are meaningful for an executing process, which physical frames they reach, and which permissions apply.

In ChrisOS, a process address space is currently represented by a per-process CR3 value pointing to a private PML4. The lower canonical half is initially private and empty except for mappings created for that process. The upper half reuses the kernel's existing PML4 entries.

This is a compact process-memory model rather than a general virtual-memory-area subsystem. Regions are represented primarily by fixed constants and process fields rather than dynamically allocated VMA descriptors.

![Current ChrisOS user address-space layout](../../assets/diagrams/address-space-layout-en.svg)

## Process table and address-space identity

The process subsystem keeps a fixed global array:

~~~text
g_proc[PROC_MAX]
PROC_MAX = 32
~~~

PID 0 is reserved for the kernel.

Each Proc currently stores:

- used;
- alive;
- scheduler state;
- CR3 physical address;
- VM-region logical byte count;
- heap break;
- number of owned pages;
- framebuffer page count;
- short process name;
- an array of virtual/physical page pairs.

The CR3 value is the architectural identity of the process translation context.

The Proc.pages array is not the page table itself. It is an ownership ledger used to remember which mapped leaf frames must be returned to PMM when the process dies.

This separation is fundamental:

~~~text
CR3/page tables -> what virtual address translates where
Proc.pages       -> which physical leaf frames this process owns
~~~

## Kernel process initialization

proc_init clears all process slots, then initializes PID 0 as the kernel process.

Its CR3 is obtained from mm_kernel_cr3, which is the paging root adopted by mm_init from the boot-time active hierarchy.

Therefore the process subsystem does not create a second kernel address space during initialization. PID 0 names the already-active kernel translation context.

g_current begins as PROC_KERNEL.

## Creating a process PML4

proc_create searches PID slots 1..PROC_MAX-1 for an unused entry.

For a free slot it calls mm_clone_kernel_space.

That function:

1. allocates and zeroes one new PML4 page;
2. obtains the current kernel PML4 through the HHDM;
3. copies entries 256 through 511 into the new PML4;
4. leaves entries 0 through 255 zero.

The structural result is:

| PML4 range | New process state |
|---|---|
| 0..255 | private and initially empty |
| 256..511 | copied references to kernel lower-level tables |

The upper-half entries are not deep-copied. They continue to point into the same kernel translation hierarchy.

A process therefore gets an independent user half while retaining the mappings required to enter and execute the kernel.

## Why the shared upper half matters

Sharing the kernel half has several benefits:

- process creation does not duplicate kernel page tables;
- system-call and exception entry can execute kernel code after a user-to-kernel transition;
- kernel virtual addresses remain stable across process CR3 switches.

It also creates a lifetime rule: process teardown must never recursively free the shared upper-half tables.

mm_free_user_space only walks PML4 entries 0..255, then frees the process PML4 itself.

Shared kernel mapping mutations also have wider TLB implications because multiple address spaces can reference the same page-table structures.

## Current lower-half validity rule

proc_map_user rejects any virtual address greater than or equal to:

~~~text
0x0000800000000000
~~~

That is the beginning of the non-lower-canonical region under the current four-level model.

The function then delegates to mm_map_cr3 and forces MM_USER into the mapping flags.

This is a broad architectural guard, not a complete process-layout policy. proc_map_user itself does not reject overlap with the heap, VM, framebuffer, stack, ELF window or other named regions.

Higher-level callers are responsible for their own interval rules.

## Current named regions

proc.h defines several fixed addresses:

| Symbol | Current address | Role |
|---|---:|---|
| ELF load window | 0x00400000..0x004fffff | native ELF PT_LOAD mappings |
| PROC_VM_VIRT | 0x02000000 | CLVM/language VM memory base |
| PROC_HEAP_VIRT | 0x04000000 | logical heap base |
| PROC_FB_VIRT | 0x06000000 | process framebuffer base |
| PROC_STACK_VIRT | 0x07F00000 | process subsystem stack-demand window |
| PROC_LIB_VIRT | 0x08000000 | reserved library base constant |

These addresses are conventions encoded directly in source.

There is no current central region table that asserts all non-overlap relationships at runtime.

## Native ELF load window

elf.c defines:

~~~text
USER_LOAD_LO = 0x400000
USER_LOAD_HI = 0x500000
~~~

Every PT_LOAD segment must fit completely within that one-megabyte window after page alignment.

The ELF loader also enforces:

- ELF64;
- little endian;
- ET_EXEC;
- x86-64 machine type;
- supported ELF version;
- at most 32 program headers;
- only PT_NULL and PT_LOAD program-header types;
- filesz <= memsz;
- no arithmetic wraparound;
- file-backed bytes stay within the input image;
- vaddr and file offset have matching page offsets;
- no W+X segment;
- program entry lies within the load window;
- program entry lies inside an executable segment;
- declared segments do not overlap each other.

Those checks make the ELF window the most explicitly permissioned region in the current user address-space model.

## ELF page materialization

elf_map_segment converts an ELF segment into process-owned 4 KiB pages.

For each page intersecting the segment:

1. allocate a physical frame;
2. zero all 4096 bytes;
3. derive PTE flags from ELF PF_W and PF_X;
4. map and record the frame through proc_map_owned;
5. copy the file-backed portion into the zeroed frame.

Permissions are derived as:

~~~text
always: PRESENT + USER
PF_W:   add WRITE
no PF_X: add NX
~~~

The loader rejects a segment with both PF_W and PF_X, implementing a concrete W^X rule for native executable mappings.

Zeroing the complete page also supplies the zero-filled portion required when memsz exceeds filesz.

## Segment overlap versus page ownership

elf_check_segment checks byte-range overlap among declared ELF segments.

proc_map_owned separately rejects mapping a virtual page already recorded in Proc.pages.

This second check matters because two non-overlapping byte ranges can still occupy the same 4 KiB page after alignment.

The current loader does not merge such segment permissions or contents. If a later segment attempts to claim a page already owned by the process, the mapping fails and the load is aborted.

This is a simpler policy than production ELF loaders that may combine adjacent segment requirements sharing a page boundary.

## Process creation before ELF mapping

elf_load validates the image first.

Only after the headers and segments pass validation does it:

1. remember the previously current PID;
2. create a new process;
3. switch CR3 to that new process;
4. map every segment;
5. configure the syscall user-copy window;
6. return the entry point.

If segment mapping fails, elf_abort destroys the new process and restores the previous process when appropriate.

This gives the loader a cleanup path for partial images.

## User-copy admissible window is separate from address-space mapping

A mapped user address is not automatically acceptable to every syscall.

syscall.c maintains a global pair:

~~~text
g_user_map_lo
g_user_map_hi
~~~

After a native ELF load, elf_load calls:

~~~text
syscall_set_user_map(USER_LOAD_LO, USER_LOAD_HI)
~~~

user_span_ok then requires syscall pointer ranges to fall inside that window before the software page-table walk occurs.

Therefore two layers exist:

1. **address-space validity**: page tables and MM_USER decide whether the process can address a page;
2. **syscall copy policy**: g_user_map_lo/hi further restrict which user pointers the current copy helpers accept.

At the reviewed revision, that copy window is global state, not stored per Proc.

This is a significant limitation for a system that may eventually run heterogeneous user-process layouts.

## VM region for language runtimes

PROC_VM_VIRT is 0x02000000.

proc_set_vm records a logical size in vm_bytes, capped at:

~~~text
PROC_PAGES * 4096
~~~

and commits the first page.

The remaining pages are demand-allocated when touched and recognized by proc_fault_demand.

compiler/lang_pipeline.c uses proc_set_vm for process-associated VM memory, including bounded CLVM-related memory requests.

The API proc_vm_ptr simply returns the fixed virtual base. Its pid argument is currently unused because the numerical virtual address is the same in every process; the active CR3 determines which physical frames the pointer names.

That is a direct illustration of virtual-memory isolation: identical virtual pointer values can identify different process-owned storage under different CR3 roots.

## Heap region

PROC_HEAP_VIRT is 0x04000000.

Each process begins with:

~~~text
heap_brk = PROC_HEAP_VIRT
~~~

proc_sbrk advances that logical break and returns the previous value.

The current upper bound is:

~~~text
PROC_HEAP_VIRT + 256 KiB
~~~

proc_sbrk does not allocate pages.

Physical commitment happens later through the page-fault path when an address below heap_brk is touched.

There is currently no shrinking operation, free-region tree, mmap allocator, brk alignment policy beyond the page-fault alignment, or per-allocation metadata at this layer.

## Process framebuffer region

PROC_FB_VIRT is 0x06000000.

proc_fb_ptr accepts a page count from 1 to 16, records fb_pages, and commits each requested page.

It returns the fixed virtual base.

The framebuffer pages in this process abstraction are therefore ordinary process-owned RAM pages associated with a framebuffer-style interface. They are not direct mappings of the physical boot framebuffer created by map_mmio_page.

The page-fault handler also recognizes the declared framebuffer range.

## Stack region and the current ABI mismatch

PROC_STACK_VIRT is 0x07F00000.

proc_create immediately commits one page at that address. proc_fault_demand allows a four-page interval beginning there.

That suggests an intended process stack region.

However, the current shell runelf path calls:

~~~text
enter_user(entry, 0x400FF8)
~~~

which places the initial user RSP inside the ELF load window rather than at PROC_STACK_VIRT.

This means two current conventions coexist:

- the generic process subsystem allocates a stack region near 0x07F00000;
- the native shell ELF launch path currently enters with a stack pointer near 0x00400FF8.

The documentation must not collapse these into one ABI.

PROC_STACK_VIRT is a real process-memory mechanism, but it is not yet the universal initial-stack location for every user execution path.

## Library base

PROC_LIB_VIRT is defined as 0x08000000.

At the reviewed revision, the core proc.c code does not implement a general dynamic-library mapping manager around that constant.

Therefore it should be treated as a reserved address convention, not evidence that shared libraries, ELF dynamic linking or per-process library VMAs are fully implemented.

## Entering user mode

enter_user receives RIP and RSP as arguments.

It prepares:

- user code selector with RPL 3;
- user data selector with RPL 3;
- RFLAGS = 0x202;
- saved kernel return RIP.

Then it builds an IRETQ frame and transitions to user mode.

Address-space switching and privilege switching are distinct operations.

A caller must already have selected the intended process CR3 before enter_user executes. elf_load does so with proc_switch(pid).

Thus user execution requires two coordinated contexts:

~~~text
translation context -> CR3
privilege/return context -> CS, SS, RIP, RSP, RFLAGS
~~~

## Switching address spaces

proc_switch enforces a current invariant: user process switching occurs only on CPU 0.

If smp_current_cpu() is not zero, it panics.

For a valid PID, proc_switch:

1. reads the process CR3;
2. updates g_current;
3. writes CR3 through mm_switch.

Writing CR3 changes the translation context and, in the current no-PCID design, has local TLB consequences.

The process model therefore does not currently support the same user address space being scheduled concurrently on multiple CPUs.

## Page ownership ledger

Proc.pages has fixed capacity PROC_PAGES = 288.

Each entry records:

~~~text
virt
phys
~~~

proc_map_owned first verifies that the virtual page is not already recorded and that capacity remains.

It then maps the supplied frame and records ownership only on success.

proc_commit allocates the frame itself and follows the same ownership invariant.

The array is linear, so page lookup and duplicate detection are O(n), bounded by 288.

There is no balanced region tree, radix tree, reverse map or reference-counted shared-page object.

## Destroying an address space

proc_destroy switches to the kernel CR3 first if the target is current.

proc_release_user then iterates Proc.pages.

For every owned frame it:

1. removes the leaf mapping from the process CR3;
2. returns the physical frame to PMM;
3. clears the ownership entry.

After leaf frames are gone, mm_free_user_space recursively frees the lower-half page-table pages and finally the process PML4.

The upper-half shared kernel structures are left intact.

Resource cleanup also closes process-owned syscall file entries and sockets.

This is a strict ownership teardown rather than reference-counted sharing.

## Shared-memory implications

The current process ownership model assumes that recorded leaf frames are individually owned by one process.

There is no general shared-memory object with reference counts.

Mapping the same physical frame into multiple processes through low-level APIs would require an ownership policy outside the present Proc.pages assumptions; otherwise one process teardown could free a frame still referenced elsewhere.

Therefore arbitrary inter-process shared memory is not an implemented general facility at this revision.

## Protection model

Different mapping producers currently apply different policies.

### ELF mappings

ELF mappings can be:

- read/execute;
- read/write/NX;
- read-only/NX depending on flags.

W+X is rejected.

### Demand mappings

proc_commit maps:

~~~text
PRESENT | WRITE | USER
~~~

without adding NX.

### Kernel mappings

Kernel and MMIO mappings use their own paths and flags.

There is no unified VMA descriptor holding desired permissions for every region.

This fragmentation is one reason the current address-space design should be viewed as an experimental stage rather than a completed VM policy layer.

## No ASLR or relocatable user-layout policy

Native ELF files are ET_EXEC and must fit the fixed 0x400000..0x500000 window.

There is no address-space layout randomization in this path.

There is also no PIE relocation engine, general dynamic linker, randomized stack position, randomized mmap base, or per-process layout seed.

The fixed addresses make the current environment deterministic and easier to debug, at the cost of flexibility and hardening.

## No fork or copy-on-write

proc_create constructs a fresh lower half and copies only the kernel upper half.

It does not clone another user process's mappings.

There is no fork-style address-space duplication, COW PTE state, reference-counted physical pages or write-fault duplication path.

Each process is created from a clean user half and populated explicitly by its loader/runtime.

## Concurrency and CPU ownership

The process table itself is global rather than per-CPU.

The explicit BSP-only process-switch invariant avoids several difficult problems:

- concurrent g_current updates;
- simultaneous user CR3 use on multiple CPUs;
- per-address-space shootdown membership;
- process migration;
- concurrent Proc.pages mutation.

This is a deliberate current simplification, not a general SMP process scheduler.

Kernel mappings still need multiprocessor TLB coherence because kernel state is shared across CPU contexts.

## Capacity and practical limits

Several fixed limits shape address-space size:

| Limit | Current value/effect |
|---|---|
| process slots | 32 total including kernel |
| owned pages per process | 288 |
| heap logical growth | 256 KiB |
| process framebuffer | 16 pages |
| demand stack window | 4 pages |
| native ELF window | 1 MiB |
| VM logical size | capped at 288 pages by proc_set_vm |

These limits interact.

ELF pages, demand pages and framebuffer pages all consume Proc.pages ownership slots. Therefore each regional maximum cannot necessarily be reached simultaneously.

The ownership array is the aggregate bound.

## Failure handling

Address-space construction can fail because:

- no process slot is free;
- PML4 allocation fails;
- initial stack commit fails;
- ELF validation fails;
- ELF page allocation fails;
- page-table allocation fails;
- Proc.pages capacity is exhausted;
- a page overlaps an already-owned page.

proc_create destroys a partially created process when its initial stack commit fails.

elf_load uses elf_abort to destroy a partially mapped image and restore the previous process context.

This provides deterministic cleanup without needing transaction logs.

## Complexity

Important current costs are:

| Operation | Cost |
|---|---|
| find free process slot | O(PROC_MAX) |
| clone kernel PML4 half | O(256) |
| find owned virtual page | O(n), n <= 288 |
| add one mapping | O(n) ownership check + fixed-depth page-table walk |
| switch address space | O(1) software operation plus architectural CR3/TLB cost |
| destroy owned leaves | O(n) |
| destroy user page tables | proportional to present lower-half table structure |
| validate ELF segment overlaps | O(number of segments²), with max 32 |

These bounds are small because the current implementation intentionally uses fixed limits.

## Validation evidence

The ELF loader has malformed-input/fuzz-oriented host tests in the repository, and documentation CI verifies multiple memory-management contracts.

MM self-tests validate basic mapping coherence.

Source invariants also expose clear review points:

- process upper/lower PML4 split;
- BSP-only switching;
- fixed virtual bases;
- ELF W^X rejection;
- entry inside executable segment;
- process page ownership cleanup.

Still-needed runtime evidence includes broader multi-process isolation tests, deliberate cross-process alias attempts, complete user stack ABI tests, permission-fault tests, and future SMP process-switch tests if the BSP-only invariant is removed.

## Current limitations

The present address-space subsystem does not yet provide:

- dynamic VMAs;
- mmap/munmap-style region management;
- ASLR;
- PIE relocation policy;
- fork;
- copy-on-write;
- general shared memory;
- reference-counted mapped frames;
- per-process syscall user-copy windows;
- generalized stack ABI across all launch paths;
- guard-page management;
- arbitrary per-region permission transitions;
- multi-CPU user-process scheduling;
- dynamic library manager tied to PROC_LIB_VIRT;
- scalable page ownership structures.

These are implementation boundaries, not architectural impossibilities.

## Revision boundary

This chapter was reconciled against ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

It documents the fixed layout, process CR3 construction, ELF window, demand regions, ownership ledger, user-copy window, current stack-layout divergence, process switching and teardown visible in the declared sources.

A future VMA manager, scheduler redesign, dynamic linker, shared-memory layer or user ABI change must trigger a new source-level review rather than being inferred from the existing constants.
