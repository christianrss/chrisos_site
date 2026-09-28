---
id: page-table-layout
lang: en
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/bootinfo.c
symbols:
  - pml4_index
  - pdpt_index
  - pd_index
  - pt_index
  - table_from_phys
  - ensure_table
  - ensure_table_flags
  - map_4k_ex
  - mm_map_cr3
  - translate_leaf
  - mm_clone_kernel_space
  - free_table_page
  - mm_free_user_space
depends_on:
  - virtual-memory
  - x86-64-memory-privilege
related:
  - page-faults
  - address-spaces
  - tlb
  - physical-memory
  - hhdm
---

# x86-64 page-table layout and entry semantics

## Scope

This chapter describes the concrete layout of the four-level x86-64 page-table hierarchy used by the current ChrisOS memory subsystem. The virtual-memory chapter explains why translation exists and how address spaces are constructed. Here the focus is narrower and more mechanical: how virtual-address bits select entries, how much address space each level covers, how entries combine physical addresses with flags, how ChrisOS creates and walks the tables, and which ownership rules prevent page-table pages from being confused with mapped data frames.

ChrisOS currently operates on the conventional four-level hierarchy:

~~~text
CR3 -> PML4 -> PDPT -> PD -> PT -> 4 KiB frame
~~~

The software walker can also terminate early on existing 1 GiB or 2 MiB huge-page entries, but the current mapping path creates 4 KiB leaves only.

![x86-64 page-table levels, spans and ChrisOS operations](../../assets/diagrams/x86-page-table-layout-en.svg)

## Why every table is one 4 KiB page

Each x86-64 paging structure in the four-level model contains 512 64-bit entries.

~~~text
512 entries * 8 bytes = 4096 bytes
~~~

That exact equality is operationally important. A page-table page has the same allocation granularity as an ordinary PMM frame. ChrisOS can therefore obtain a new table with pmm_alloc, access it through the HHDM, clear its 512 entries, and link its physical address into the parent entry.

No separate page-table allocator exists in the current implementation. The PMM does not know whether an allocated frame will hold process data, a page table, a kernel buffer, or another object; that semantic ownership is established by the caller.

## Virtual-address decomposition

For a 4 KiB page in the current four-level model:

| Field | Virtual-address bits | Width | Selects |
|---|---:|---:|---|
| PML4 index | 47..39 | 9 | one of 512 PML4 entries |
| PDPT index | 38..30 | 9 | one of 512 PDPT entries |
| PD index | 29..21 | 9 | one of 512 PD entries |
| PT index | 20..12 | 9 | one of 512 PTEs |
| Page offset | 11..0 | 12 | byte within a 4 KiB page |

The helper functions in mm.c implement those shifts directly.

For virtual address V:

~~~text
PML4(V) = (V >> 39) & 0x1ff
PDPT(V) = (V >> 30) & 0x1ff
PD(V)   = (V >> 21) & 0x1ff
PT(V)   = (V >> 12) & 0x1ff
OFF(V)  = V & 0xfff
~~~

Because every index contains nine bits, each level multiplies the span represented by one entry by 512.

## Coverage span of each entry

The hierarchy can be reasoned about from the bottom upward.

One PTE maps one 4 KiB page:

~~~text
PT entry span = 2^12 = 4 KiB
~~~

A page table has 512 PTEs:

~~~text
PD entry span = 512 * 4 KiB = 2 MiB
~~~

A page directory contains 512 entries:

~~~text
PDPT entry span = 512 * 2 MiB = 1 GiB
~~~

A PDPT contains 512 entries:

~~~text
PML4 entry span = 512 * 1 GiB = 512 GiB
~~~

And 512 PML4 entries describe 256 TiB of virtual-address combinations before canonical-address rules divide the usable range into lower and upper halves.

| Entry type | Span represented by one entry |
|---|---:|
| PTE | 4 KiB |
| PDE | 2 MiB |
| PDPTE | 1 GiB |
| PML4E | 512 GiB |

This span arithmetic explains why a sparse mapping may still require multiple metadata pages: mapping one isolated 4 KiB page can require one PDPT, one PD, and one PT page beneath an already-existing PML4.

## Canonical addressing and PML4 halves

In the four-level 48-bit model, bits above bit 47 must form the canonical extension of bit 47. The hardware therefore divides the usable canonical space into a lower region and an upper region separated by a non-canonical hole.

At the PML4 level, ChrisOS uses a convenient consequence of that split:

- entries 0..255 are treated as the user half;
- entries 256..511 are treated as the kernel half.

mm_clone_kernel_space allocates a new PML4, leaves the lower 256 entries zero, and copies the upper 256 entries from the kernel PML4.

A process therefore receives private roots for future user mappings while retaining shared references to the kernel translation hierarchy.

The copying boundary is structural, not a security policy by itself. Effective user access still depends on page-table permission bits and the privilege mode of the access.

## General 64-bit entry shape

An x86-64 paging entry combines:

1. low-order control/status bits;
2. a page-aligned physical address or next-table address;
3. additional architectural bits at the high end, including NX where supported and enabled.

ChrisOS uses:

~~~c
MM_PRESENT = 1 << 0
MM_WRITE   = 1 << 1
MM_USER    = 1 << 2
MM_PWT     = 1 << 3
MM_PCD     = 1 << 4
MM_NX      = 1 << 63
~~~

and masks ordinary table/frame addresses with:

~~~text
MM_ADDR_MASK = 0x000ffffffffff000
~~~

The lower 12 bits are therefore not part of the 4 KiB-aligned frame address.

The kernel source does not attempt to expose every architectural PTE bit through named MM constants. Accessed, dirty, global, PAT-related details and other architectural state are not currently modeled as a complete software abstraction.

## Present is a path property

For a normal 4 KiB walk, the hardware must encounter PRESENT at every required level.

A present leaf below a non-present parent is unreachable. Conversely, a present intermediate entry merely states that the next paging structure exists; it does not imply that a particular final virtual page is mapped.

ChrisOS follows this same rule in software walkers. translate_leaf returns failure immediately when the selected entry at any level lacks MM_PRESENT.

This is why an empty newly allocated table is useful: the parent becomes present and points to a valid paging structure, while every child entry initially remains zero and therefore non-present.

## Physical address versus flags

When following an intermediate entry, ChrisOS removes flag bits before converting the child-table physical address to an HHDM pointer.

table_from_phys applies MM_ADDR_MASK and then bootinfo_phys_to_virt.

The conceptual operation is:

~~~text
child_phys = entry & ADDRESS_MASK
child_virt = HHDM(child_phys)
~~~

The physical address stored in a page table is not directly dereferenced as a C pointer. The kernel accesses that physical page through its direct-map virtual alias.

That distinction is central to avoiding accidental assumptions that physical and virtual addresses are numerically identical.

## Creating an intermediate table

ensure_table handles kernel mappings.

If a selected parent entry is absent:

1. allocate one PMM frame;
2. obtain its HHDM pointer;
3. clear all 512 entries;
4. store the child's physical address in the parent;
5. set PRESENT and WRITE;
6. return the child table's virtual pointer.

If the parent entry already exists and has PS set, the function panics because map_4k cannot descend through a huge-page leaf.

If the entry is an ordinary non-leaf, the existing child table is reused.

The time cost is constant with respect to address-space size. The expensive part of creating a table is clearing 4096 bytes; once it exists, future neighboring mappings reuse it.

## User mappings and permission propagation

ensure_table_flags is the recoverable variant used by mm_map_cr3.

For user mappings, extra contains MM_USER. When a missing intermediate table is created, the parent entry becomes:

~~~text
child_phys | PRESENT | WRITE | USER
~~~

When an intermediate table already exists but its parent entry lacks USER, ensure_table_flags upgrades that parent entry by ORing MM_USER.

This matches a critical x86 paging property: permissions are accumulated along the translation path.

For a user access to succeed, the hierarchy cannot contain a supervisor-only ancestor. Therefore, setting USER only on the final PTE would be insufficient.

Similarly, write permission is constrained by the path. ChrisOS makes newly created intermediate entries writable and lets the leaf flags determine whether the individual mapping is writable.

The current routines do not construct intermediate NX entries; execution control in mappings created by this API is expressed at the leaf through MM_NX.

## Leaf installation

After PML4, PDPT, PD, and PT pointers have been resolved, the 4 KiB mapping path writes:

~~~text
PTE = (phys & MM_ADDR_MASK) | flags | MM_PRESENT
~~~

Both virtual and physical inputs must be 4 KiB aligned.

The offset is not stored in the PTE. During hardware translation, the low 12 bits of the original virtual address are appended to the page-aligned physical base from the leaf.

Thus for a 4 KiB leaf:

~~~text
physical = (PTE & MM_ADDR_MASK) | (virtual & 0xfff)
~~~

## Huge-page leaf semantics

The PS bit changes the meaning of a PDPT or PD entry.

In the current software translator:

- PS at PDPT level represents a 1 GiB leaf;
- PS at PD level represents a 2 MiB leaf;
- PT level represents a 4 KiB leaf without PS.

The physical masks and offsets differ:

| Leaf level | Page size | Base mask used by current walker | Offset mask |
|---|---:|---|---|
| PDPT | 1 GiB | 0x000fffffc0000000 | 0x3fffffff |
| PD | 2 MiB | 0x000fffffffe00000 | 0x1fffff |
| PT | 4 KiB | MM_ADDR_MASK | 0xfff |

translate_leaf can therefore inspect huge mappings inherited from the boot-created hierarchy.

The mapping functions do not create those huge leaves, and ensure_table/ensure_table_flags refuse to descend through them. ChrisOS has no current split operation that converts one huge mapping into a lower-level table tree.

## Recursive software walk

translate_leaf receives:

- the physical address of the current table;
- the virtual address being translated;
- a level number;
- output pointers for physical address and flags.

The level selects which 9-bit index to use.

If the entry is absent, translation fails.

If PS is set, or the walk has reached level zero, the function computes the final physical address and returns the leaf entry as flags.

Otherwise it recurses using the physical address encoded in the entry as the next table.

Because the hierarchy depth is bounded, recursion depth is also bounded. This is O(1) with respect to the amount of mapped virtual memory.

## Kernel-specific software walk

mm_virt_to_phys implements a non-recursive version specialized to the kernel root.

It explicitly evaluates PML4, PDPT, PD, and PT in order and supports the same huge-page termination at PDPT and PD.

The function returns zero for an absent mapping.

Zero is therefore a sentinel in this API, which means callers must not treat it as a general representation capable of distinguishing an unmapped address from a hypothetical mapping that legitimately resolves to physical address zero. The current callers and memory layout operate within that interface contract.

## Table allocation failure semantics

There are two allocation policies.

For map_4k, alloc_zero_table panics if PMM cannot supply a table page.

For mm_map_cr3, alloc_zero_table_try returns zero and the mapping routine returns -1.

However, mm_map_cr3 does not undo intermediate tables created earlier in the same call. If allocation fails after one or more parent tables were linked, those tables remain in the hierarchy.

This design favors implementation simplicity and reuse over transactional semantics. It remains safe from an ownership perspective because the intermediate pages are reachable and later reclaimed with the user table tree, but callers must not assume a failed mapping leaves the hierarchy unchanged.

## Sharing the kernel half

A new process PML4 receives copies of entries 256..511 from the kernel root.

The copy operation copies 64-bit entries, not the page-table pages beneath them. Therefore multiple process PML4s can reference the same kernel PDPT/PD/PT structures.

This has two consequences.

First, memory overhead is reduced because the kernel mappings are not duplicated per process.

Second, a mutation of a shared kernel mapping is conceptually visible to every address space that reaches that same lower-level structure. TLB coherence must then be considered across CPUs and address spaces that may have cached the prior translation.

This is why shared-kernel mapping teardown is coupled to the TLB-shootdown protocol rather than to process-local unmapping alone.

## Freeing user page-table structures

mm_free_user_space receives the physical address of a process PML4.

It rejects zero, an uninitialized MM state, and the kernel root itself.

Then it walks only PML4 entries 0..255.

For each present non-huge entry, free_table_page recursively frees lower-level table pages. The recursion is deliberately structured so that it does **not** free frames named by final PTE leaves.

That separation is essential:

~~~text
page-table frame ownership -> MM tree teardown
mapped data-frame ownership -> process Proc.pages teardown
~~~

Before mm_free_user_space runs, proc_release_user is responsible for clearing leaf mappings and returning owned data frames to PMM.

Finally, mm_free_user_space releases the process PML4 frame itself.

## Why the recursive free stops before leaf frames

free_table_page receives a table frame and a level.

When level is greater than one, it examines entries and recursively visits present non-PS child table pages.

At the level representing a PT page, recursion stops and the PT page itself is freed without walking PTEs as though their physical addresses were more paging structures.

That termination rule encodes the ownership boundary between page-table metadata and mapped objects.

If the routine recursively followed ordinary PTEs, it would interpret application data frames as page tables and corrupt memory ownership.

## Alignment invariants

Page-table structure addresses and 4 KiB leaf frame addresses must be page aligned.

ChrisOS enforces alignment at its mapping APIs:

~~~text
virt % 4096 == 0
phys % 4096 == 0
~~~

map_4k treats violation as fatal. mm_map_cr3 returns -1.

Alignment makes the low address bits available for entry flags and guarantees that masking with MM_ADDR_MASK recovers the frame base.

Huge-page leaves impose stronger alignment requirements architecturally; the current software translator assumes inherited huge entries are already valid.

## Page-table memory overhead

A fully populated four-level tree would be enormous, but real address spaces are sparse and tables are allocated on demand.

For a single isolated 4 KiB mapping under an existing PML4, the worst case is:

- one PDPT page;
- one PD page;
- one PT page;
- one data frame owned separately.

That is 12 KiB of new page-table metadata for the first isolated 4 KiB mapping in a distant region.

The overhead falls sharply for locality:

- one PT page can describe 512 contiguous 4 KiB pages = 2 MiB;
- one PD page can point to 512 PT pages = 1 GiB;
- one PDPT page can describe 512 GiB through its PD children.

Dense virtual regions therefore amortize metadata much better than widely scattered single-page mappings.

## Synchronization

Page tables are mutable shared data structures.

ChrisOS protects walks and mutations with mm_lock. That prevents two kernel execution contexts from concurrently creating conflicting child tables or observing a parent entry while another operation is only partially modifying the hierarchy.

The lock protects the memory representation of the tables. It does not by itself invalidate TLB entries already cached in CPUs.

After a mapping change, the required invalidation depends on scope:

- a local page can use INVLPG;
- a broad local refresh can reload CR3;
- shared mappings visible on other CPUs require the multiprocessor TLB protocol.

Page-table consistency and TLB coherence are related but distinct correctness problems.

## Failure modes

Important current failure cases include:

| Condition | Current behavior |
|---|---|
| map before MM initialization | kernel map path panics; mm_map_cr3 fails |
| unaligned kernel map | panic |
| unaligned mm_map_cr3 | -1 |
| PMM exhaustion in kernel table creation | panic |
| PMM exhaustion in process table creation | -1, possibly with reachable partial intermediates |
| PS entry encountered in 4 KiB creation path | panic |
| absent entry during software translation | translation failure |
| attempt to free kernel CR3 as user space | ignored |
| shared mapping changed without adequate TLB invalidation | stale translation risk |

The last failure is not visible by inspecting page-table memory alone. A correct PTE in RAM can coexist temporarily with an obsolete TLB entry.

## Validation boundary

The current MM self-test validates that a PMM frame mapped through a new 4 KiB leaf aliases the same physical storage visible through HHDM. It also exercises the fixed MMIO mapping path with the LAPIC page.

Those tests support the basic entry construction and translation path.

They do not exhaustively test:

- every permission combination;
- every canonical boundary;
- huge-page splitting;
- malformed inherited page tables;
- all intermediate-allocation failure positions;
- concurrent creation of the same missing path;
- every remote TLB race.

The absence of those tests should not be interpreted as evidence that those cases have been proven.

## Current design boundary

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, the implemented page-table model is:

- four-level x86-64 paging;
- 4 KiB mappings created by ChrisOS;
- recognition of inherited 2 MiB and 1 GiB leaves during translation;
- sparse intermediate-table allocation from PMM;
- HHDM access to paging structures;
- shared upper-half kernel PML4 entries;
- private lower-half process table trees;
- explicit USER propagation for user mappings;
- no automatic huge-page creation or split;
- no five-level paging;
- no transactional rollback of partially created paths;
- no PCID-specific page-table context management.

These constraints define the actual implementation and should remain separate from future architectural goals.

## Revision boundary

This chapter was reconciled against ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56. The source paths and symbols in the frontmatter are the authority for implementation claims. Changes to the boot paging hierarchy, address-space split, page-table allocator, permission policy, or huge-page handling require re-review.
