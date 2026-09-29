---
id: virtual-memory
lang: en
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/tlb_proto.c
  - kernel/metal/tlb_proto.h
symbols:
  - mm_init
  - mm_map_cr3
  - map_4k
  - map_4k_nosync
  - mm_translate
  - mm_virt_to_phys
  - mm_switch
  - mm_clone_kernel_space
  - mm_unmap_cr3
  - unmap_4k
  - mm_free_user_space
  - mm_flush_tlb
  - mm_tlb_quarantine
depends_on:
  - physical-memory
  - hhdm
  - x86-64-memory-privilege
related:
  - page-table-layout
  - page-faults
  - address-spaces
  - tlb
  - tlb-shootdown
  - processes-syscalls
---

# Virtual memory and page-table management

## Scope

Virtual memory separates the addresses used by software from the physical locations that hold bytes. On x86-64, CR3 selects the current translation hierarchy; the CPU combines that hierarchy with page-table permissions and TLB state to translate a virtual address into a physical address or raise an exception.

ChrisOS uses virtual memory for several distinct purposes:

- preserving a shared higher-half kernel mapping;
- creating private user address spaces;
- mapping process pages on demand;
- mapping ordinary kernel aliases;
- reserving a dedicated MMIO window;
- translating virtual addresses for validation and debugging;
- isolating user and supervisor access;
- coordinating mapping teardown with TLB invalidation and delayed physical reuse.

The current implementation already contains one of the most important systems-level separations in the project:

~~~text
PMM owns physical frames.
MM owns virtual-to-physical translations.
TLB protocol governs when stale translations are no longer usable.
~~~

These three responsibilities must remain distinct for teardown to be correct.

![Relationship between PMM ownership, page tables, CR3, TLB invalidation and physical reuse](../../assets/diagrams/virtual-memory-mapping-en.svg)

## Translation model

A CPU instruction issues a virtual address.

Conceptually:

~~~text
virtual address
   -> TLB lookup
      -> hit: cached translation and permissions
      -> miss: hardware page-table walk from CR3
            -> present and permitted: physical address
            -> missing or forbidden: page fault
~~~

Software modifies the in-memory page tables, but the CPU may continue using a cached TLB entry after a PTE changes. Therefore changing page-table memory does not automatically make every CPU observe the new mapping.

That distinction is why unmapping and physical-frame reuse require additional synchronization.

## Four-level x86-64 structure

ChrisOS uses the conventional four-level layout:

~~~text
PML4 -> PDPT -> PD -> PT -> 4 KiB frame
~~~

For a normal 4 KiB page:

~~~text
virtual bits 47..39 -> PML4 index
virtual bits 38..30 -> PDPT index
virtual bits 29..21 -> PD index
virtual bits 20..12 -> PT index
virtual bits 11..0  -> byte offset
~~~

Each table contains 512 64-bit entries because:

~~~text
4096 bytes / 8 bytes per entry = 512
~~~

Each index is therefore 9 bits.

ChrisOS helper functions compute each index by shifting and masking with 0x1ff.

The exact entry geometry is covered separately in page-table-layout; this chapter focuses on mapping lifecycle and ownership.

## CR3 and the kernel root

During mm_init, ChrisOS reads the current CR3 register:

~~~text
mm_cr3_phys = CR3 & MM_ADDR_MASK
~~~

The kernel therefore adopts the page-table root already active when control reaches MM initialization rather than constructing a new top-level hierarchy first.

mm_kernel_cr3 exposes that physical root.

mm_switch writes another physical root into CR3.

CR3 is a physical-address contract. Passing an HHDM virtual pointer instead of a page-table physical address would be incorrect.

## Initialization ordering

The current boot path establishes this order:

~~~text
Limine creates boot mappings
    -> bootinfo_init validates HHDM and memory map
    -> pmm_init owns physical frames
    -> mm_init adopts current CR3
    -> heap and process systems initialize
~~~

mm_init initializes the MM lock and TLB runtime state, captures CR3, initializes the MMIO allocation cursor and marks the MM layer ready.

It then translates the Limine framebuffer virtual address with mm_virt_to_phys.

If no physical translation exists, boot panics.

That check confirms that the page-table walk machinery can resolve an important pre-existing mapping.

## Page-table pages come from PMM

When ChrisOS needs a new intermediate table, it allocates one 4 KiB physical frame from PMM.

alloc_zero_table_try:

1. calls pmm_alloc;
2. converts the physical frame to an HHDM pointer;
3. clears all 512 entries;
4. returns the physical address.

Zeroing is necessary because an unused table must begin with all entries non-present. Reusing arbitrary RAM without clearing it could interpret old data as valid mappings.

The dependency direction is:

~~~text
MM -> PMM
~~~

PMM does not depend on MM for ordinary frame bookkeeping.

## Mapping the active kernel address space

map_4k maps one aligned 4 KiB physical frame into one aligned virtual page of the current kernel root.

It validates alignment, acquires the MM lock, and walks PML4, PDPT, PD and PT.

Missing intermediate tables are created through ensure_table.

A new intermediate entry receives PRESENT and WRITE.

At the leaf:

~~~text
PTE = physical_base | flags | PRESENT
~~~

After releasing the lock, map_4k executes invlpg for the mapped virtual address.

map_4k_nosync performs the same PTE update but skips that local invalidation.

The nosync form is therefore a specialized primitive whose caller must understand when immediate local invalidation is unnecessary or coordinated elsewhere.

## Mapping an arbitrary CR3

mm_map_cr3 installs a 4 KiB mapping into a supplied address-space root.

It differs from the kernel-only path:

- invalid state or alignment returns -1 instead of panicking;
- missing page tables are allocated through a fallible helper;
- user mappings propagate the USER bit through intermediate entries;
- the function does not switch to the target CR3;
- the function does not itself perform a remote TLB shootdown.

The user-bit propagation is essential.

If the leaf PTE is user-accessible but any parent entry lacks USER, ring 3 cannot traverse the hierarchy.

Thus user accessibility is a property of the whole walk, not only the leaf.

## Partial allocation on failure

ensure_table_flags allocates intermediate tables incrementally.

If allocation fails at a deeper level, mm_map_cr3 returns -1.

Intermediate tables already inserted at higher levels can remain installed.

That does not create a leaf mapping to the requested frame, but the operation is not transactional in the sense of rolling back every table page allocated before failure.

Those table pages remain owned by the address-space hierarchy and are later reclaimed during address-space destruction.

Therefore the stronger statement “mapping failure leaves no structural change” would be incorrect for the current code.

## Mapping versus physical ownership

A PTE can refer to a physical frame without implying that MM owns that frame.

Examples:

- process page frames are tracked by process ownership state;
- page-table frames are owned by the MM hierarchy;
- device physical addresses are not PMM allocations;
- framebuffer memory is not an ordinary PMM frame;
- one physical frame can have several virtual aliases.

Therefore:

~~~text
remove PTE != free physical frame
free physical frame != remove all PTEs
~~~

The caller must coordinate both layers.

## Process address spaces

mm_clone_kernel_space allocates a fresh PML4 and copies entries 256 through 511 from the kernel PML4.

Those entries represent the upper half.

The lower 256 PML4 slots remain initially empty.

Conceptually:

~~~text
process CR3
  lower half: private user mappings
  upper half: shared kernel mappings
~~~

This keeps kernel code, HHDM and other privileged mappings reachable while a process CR3 is active.

The copy is of PML4 entries, not a deep copy of all higher-half trees. The process roots therefore share the underlying higher-half structures referenced by those entries.

## Privilege separation

The kernel/user split is not enforced merely by using high and low virtual addresses.

Page-table permission bits matter.

User pages are mapped with USER, and intermediate entries are upgraded with USER when required.

Kernel shared mappings remain supervisor-only.

A ring-3 access therefore needs a chain of entries whose privilege flags permit user traversal and a leaf whose write and execute permissions permit the requested operation.

This is part of the hardware isolation boundary.

## Writable and executable state

ChrisOS exposes mapping flags including:

~~~text
WRITE
USER
PWT
PCD
NX
~~~

NX uses bit 63.

A data page can therefore be marked non-executable, assuming the platform and paging configuration support NX as expected.

The current mapping API does not provide a high-level W^X policy object. It accepts raw flags from callers.

Security therefore depends on callers choosing correct permissions.

The dedicated jit-memory chapter is the appropriate place for executable-memory policy.

## MMIO mapping window

Device physical memory is mapped through map_mmio_page.

ChrisOS reserves a virtual window beginning at:

~~~text
0xffffffff90000000
~~~

and allows 256 4 KiB slots, totaling 1 MiB.

The mapping flags are:

~~~text
PRESENT | WRITE | PWT | PCD | NX
~~~

This distinguishes MMIO from ordinary RAM and HHDM use.

mmio_next advances monotonically.

There is currently no MMIO-window free and reuse allocator.

When the 256-page window is exhausted, the kernel panics.

## Explicit virtual-to-physical translation

ChrisOS contains two related helpers.

mm_translate walks a supplied CR3 hierarchy and returns both physical address and leaf flags.

It recognizes:

- 4 KiB leaves;
- 2 MiB large pages at PD level;
- 1 GiB large pages at PDPT level.

mm_virt_to_phys walks the current kernel root and returns physical address zero when no mapping exists.

The two APIs serve different callers: one is address-space explicit and exposes flags; the other is a current-kernel convenience path.

## Large-page awareness

The mapping path map_4k does not split an existing large page.

If an intermediate entry has the page-size bit set, ensure_table panics because the 4 KiB mapping path cannot descend through that leaf.

By contrast, translation helpers understand 1 GiB and 2 MiB leaves.

The current implementation can therefore observe large mappings inherited from the boot environment but does not generically edit a 4 KiB subpage inside them.

That difference must be preserved in documentation.

## Unmapping a kernel page

unmap_4k walks the kernel hierarchy.

If an expected level is absent or is a large-page leaf, the function returns without modification.

For a normal 4 KiB leaf, it writes zero into the PTE and then executes local invlpg.

It does not free the physical frame.

The caller is responsible for determining whether and when that frame can return to PMM.

## Unmapping from a specific address space

mm_unmap_cr3 clears one 4 KiB leaf in the specified hierarchy.

After mutation, it reads the current CR3.

Only if the modified CR3 is currently active on this CPU does it execute local invlpg.

If another CPU or later execution context may have cached that translation, broader TLB synchronization is still necessary.

A page-table update alone is therefore not a complete multi-CPU teardown protocol.

## TLB coherence and physical reuse

Suppose a PTE is cleared and its physical frame is immediately returned to PMM.

Another CPU could still have the old virtual-to-physical translation cached.

That CPU might write through the stale TLB entry into a frame already reassigned to a different owner.

Safe teardown requires:

~~~text
remove mapping
    -> invalidate and acknowledge stale translations
    -> prove reuse is safe
    -> free or reap physical frame
~~~

ChrisOS implements a TLB runtime and shootdown protocol plus a small physical-frame quarantine for cases where reuse is not yet safe.

The detailed distributed protocol belongs in tlb-shootdown.

## Quarantine

mm_tlb_quarantine either:

- frees frames immediately when the runtime says reuse is safe; or
- appends the range to a fixed quarantine array.

The quarantine can hold 128 ranges.

mm_tlb_reap returns quarantined ranges to PMM only when the TLB runtime reports reuse-safe state.

This is a memory-lifetime mechanism rather than a translation mechanism.

It connects TLB synchronization back to PMM ownership.

## MM lock

Page-table manipulation is serialized by mm_lock.

mm_enter is not a plain spin loop. While waiting, it invokes mm_tlb_poll.

That lets a CPU waiting for the MM lock still service pending TLB runtime work, reducing the risk that it blocks distributed invalidation progress only because it is waiting for page-table mutation.

The loop then attempts an atomic CAS and executes pause between retries.

This is a specialized integration between locking and TLB coordination.

## Why shootdown does not hold mm_lock

The source explicitly warns against waiting for remote TLB acknowledgements while holding mm_lock.

An interrupt or remote path may require memory-management progress to acknowledge the protocol.

Holding the page-table lock across the whole distributed wait could create a circular stall.

ChrisOS therefore separates:

1. page-table mutation under mm_lock;
2. distributed TLB synchronization under separate shootdown state.

Lock scope is part of the correctness model.

## Address-space destruction

mm_free_user_space walks the lower 256 PML4 entries of a non-kernel address space.

For non-large-page trees it recursively frees intermediate page-table pages and clears the PML4 entries.

Finally it frees the PML4 frame itself.

The upper half is intentionally not traversed or freed because it references shared kernel structures.

Leaf user-data frames are also not freed by this function.

The source contract states that leaf frames remain owned by the process page list.

This prevents double-free between process ownership and page-table teardown.

## Process teardown division of labor

The process layer tracks owned user pages.

During teardown it can unmap each process page and return its physical frame.

Separately, mm_free_user_space reclaims page-table structure pages.

Thus:

~~~text
process page list -> owns leaf data frames
MM hierarchy      -> owns intermediate page-table frames
shared kernel     -> not freed with process
~~~

This ownership split is one of the central invariants in the current system.

## CR3 switching and local flush

Writing CR3 changes the active translation root.

mm_flush_tlb reads and rewrites the current CR3 value to obtain the conventional local flush behavior associated with reloading the root.

The exact architectural effects can depend on features such as PCID and global mappings, but the current code uses CR3 reload as a coarse local flush primitive.

For one page, invlpg is the targeted primitive.

## Self-test

mm_selftest validates several integration properties.

It:

1. allocates a physical page from PMM;
2. maps it at a fixed test virtual address;
3. writes 0x00c0ffee through that mapping;
4. checks the value through the HHDM alias;
5. maps the LAPIC physical page through the MMIO window;
6. reads LAPIC ID;
7. compares and logs it with boot information.

The first test proves that two virtual aliases resolve to the same physical frame.

The LAPIC path validates that dedicated MMIO mapping can reach a real platform device.

The test does not exhaustively verify user privilege, large-page editing, multi-CPU shootdown, or address-space destruction.

## Failure policies

The MM layer mixes panic and return-code policies.

Examples:

- map_4k before initialization: panic;
- misaligned kernel map_4k: panic;
- page-table allocation failure in kernel mapping: panic;
- fallible mm_map_cr3: returns -1;
- invalid or unmapped translation: return failure or zero;
- exhausted MMIO virtual window: panic;
- unsupported large page in the 4 KiB mapping path: panic.

Callers must know which interface is recoverable.

## Complexity

A four-level walk is bounded by four table lookups for a 4 KiB mapping.

Ignoring PMM allocation:

~~~text
map or translate or unmap hierarchy walk = O(levels) = O(1)
~~~

because the number of architectural levels is fixed.

Allocating missing intermediate tables adds at most three PMM allocations for a new 4 KiB leaf under an existing PML4 root.

Destroying an address space is different: recursive freeing can visit many populated table pages and is proportional to the page-table structure size.

TLB shootdown cost depends on CPU count and responsiveness rather than page-table depth alone.

## Security implications

Virtual memory is the primary hardware isolation boundary between user processes and privileged kernel memory.

Security failures include:

- propagating USER into a mapping that should remain supervisor-only;
- leaving writable or executable permissions broader than intended;
- freeing a frame before stale mappings disappear;
- mapping MMIO with normal-RAM assumptions;
- accepting a user pointer without validating its translation and permissions.

The MM implementation supplies mechanisms.

Higher layers must still enforce policy.

## Current limitations

The current MM layer has important limits:

- four-level paging assumptions in index helpers;
- no generic five-level paging support;
- no generic large-page creation or splitting API;
- fixed 1 MiB MMIO virtual window;
- no MMIO unmap and reuse allocator;
- no copy-on-write;
- no page-table reference counting;
- no transactional rollback of intermediate tables after fallible mapping failure;
- shared upper-half structures require careful synchronization;
- mapping APIs expose low-level flags;
- address-space teardown depends on higher-level leaf ownership;
- distributed TLB correctness is delegated to a separate runtime protocol.

These are implementation facts, not x86-64 requirements.

## Source map

kernel/metal/mm.c implements page-table walking, table allocation, kernel and process mappings, MMIO mappings, address-space cloning, unmapping, translation helpers and TLB-related quarantine.

kernel/metal/mm.h defines the public mapping flags and contracts.

kernel/metal/pmm.c supplies physical page-table frames.

kernel/metal/proc.c owns process leaf pages and process CR3 lifecycles.

kernel/metal/tlb_proto.c and tlb_proto.h provide the distributed stale-translation protocol used during reuse-sensitive teardown.

These implementation claims were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
