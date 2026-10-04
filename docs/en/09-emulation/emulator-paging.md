---
id: emulator-paging
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/boot.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_translate
  - canonical
  - read_pte
  - write_pte
  - chris_va_read
  - chris_va_write
  - install_tables
depends_on:
  - emulator-exceptions
  - x86-64-memory-privilege
  - virtual-memory
related:
  - chrisvm-memory-map
  - chrisvm-chriscpu
  - higher-half-kernel
---

# Four-level paging and virtual-memory translation in ChrisCPU

## Scope

ChrisCPU implements a compact x86-64 page-table walker in cpu/emulator/mmu.c. The walker translates guest virtual addresses to modeled physical addresses and enforces a useful subset of long-mode paging permissions. It supports ordinary 4 KiB pages plus 2 MiB and 1 GiB large pages, tracks Accessed and Dirty bits, models supervisor write protection through CR0.WP, applies user/supervisor permission, and implements NX execution checks when EFER.NXE is enabled.

The same module also owns the virtual read/write wrappers used by instruction fetch, operands, descriptor-table access and exception-frame construction. Those wrappers translate one page-sized chunk at a time and convert translation outcomes into guest exceptions or monitor exits.

The implementation is deliberately smaller than a complete Intel/AMD MMU. There is no TLB, no PCID, no five-level paging, no SMEP/SMAP, no protection keys and no reserved-bit validation. Two known implementation gaps are locked into the documentation test suite so that future changes cannot silently invalidate the documented boundary.

This chapter describes revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Paging-disabled identity path

The first branch in chris_translate checks CR0.PG. If paging is clear, translation is direct:

    physical = virtual

No page-table memory is read and no permission bits are interpreted.

The independent MMU contract test verifies both the identity result and zero physical page-table reads for this path.

This behavior is useful for isolated tests, although normal chris_boot configures paging before guest execution.

## Address canonicality

With paging enabled, ChrisCPU first applies a 48-bit long-mode canonical-address test. It shifts the virtual address by 47 and accepts only:

    top == 0
    or
    top == 0x1ffff

Therefore bit 47 must be sign-extended through bits 63..48.

A noncanonical address returns a distinct internal result, minus two. chris_va_read and chris_va_write translate that result into #GP with error code zero rather than #PF.

This is a four-level, 48-bit model. CR4.LA57 and 57-bit canonical addresses are not implemented.

## CR3 and the four-level walk

The root table address is:

    table = CR3 AND NOT 0xfff

The low twelve CR3 bits are discarded. PCID semantics are not modeled.

The walker uses four index shifts:

| Level | Structure | Virtual bits |
|---:|---|---|
| 0 | PML4 | 47..39 |
| 1 | PDPT | 38..30 |
| 2 | PD | 29..21 |
| 3 | PT | 20..12 |

At each level:

    index = (va >> shift[level]) AND 0x1ff
    entry_address = table + index * 8

The 64-bit entry is fetched with chris_phys_read. This is a physical-memory access: the page-table walk does not recursively translate its own table addresses.

If the physical page-table entry cannot be read, chris_translate returns minus three. This is intentionally different from a guest not-present page fault.

## Present checks and error codes

If bit 0 of an entry is clear, translation returns the normal page-fault result and builds an error code from access context.

For a not-present entry:

- W/R, bit 1, is set for a write;
- U/S, bit 2, is set when CPL is 3;
- I/D, bit 4, is set for an instruction fetch;
- P, bit 0, remains clear.

The implementation carries these checks through every traversed level. A missing PML4E, PDPTE, PDE or PTE therefore faults before any lower-level access.

The page-fault wrapper stores the faulting virtual address in CR2 and raises vector 14.

## User/supervisor permission propagation

ChrisCPU defines user access as arch.cpl equal to three.

At every present level, a user access requires the U/S bit in that entry. If any ancestor or leaf is supervisor-only, the translation fails with P set because the page is present but protection denied.

The contract fixture explicitly verifies denial at an ancestor entry, not merely at the leaf. This matters because effective x86 page permissions are the intersection of the hierarchy.

The model distinguishes only CPL 3 from non-CPL-3 for this permission decision. Full ring semantics and segmentation privilege interaction are outside the walker.

## Write permission and CR0.WP

For a write, each traversed entry is checked for the R/W bit.

If R/W is clear:

- a user access faults;
- a supervisor access faults when CR0.WP is set;
- a supervisor access is allowed when CR0.WP is clear.

The independent contract test exercises all three cases. It confirms that turning off CR0.WP permits the supervisor write but does not grant the same write to CPL 3.

This is a useful and architecturally significant part of the emulator because operating-system code often depends on CR0.WP to protect read-only mappings even while running in the kernel.

## NX execution checks

Execution uses access class two. When EFER.NXE is enabled, bit 63 of every traversed entry is treated as NX. Encountering NX during an instruction fetch returns a protection page fault with:

    P = 1
    I/D = 1
    U/S according to CPL

The contract fixture verifies the user execution case and expects error code 21 decimal, corresponding to P, U/S and I/D.

When EFER.NXE is clear, the walker does not treat bit 63 as an execution denial.

The boot protocol currently sets LME and LMA but not NXE, so NX is not active in the default identity map unless guest software enables it.

## Accessed bit

For every present entry, the walker checks bit 5. If it is clear, ChrisCPU sets it in the local entry value and attempts to write the entry back to physical memory.

Thus a successful cold 4 KiB walk normally touches four entries and attempts four Accessed-bit updates.

The contract test verifies that all four levels acquire A on a successful read.

There is no TLB in this implementation. Later translations reread page-table entries from modeled physical memory, although already-set A bits avoid repeated writes.

## Dirty bit

Dirty bit 6 is updated only at the leaf that terminates a write translation.

For a 4 KiB page, the PTE gets D on a write. For a 2 MiB or 1 GiB large page, the large-page entry receives D.

A read leaves D clear.

The fixture explicitly verifies both behaviors.

## 4 KiB leaves

At level three, the physical address is currently formed as:

    physical = (entry AND NOT 0xfff) OR (va AND 0xfff)

This is concise but contains a known address-mask defect. NOT 0xfff preserves high non-address attribute bits, including NX at bit 63.

If a 4 KiB leaf has NX set and the current access is a data read, the translation is allowed but bit 63 leaks into the returned physical address.

The independent probe intentionally characterizes this gap. It expects a translated address with the high NX bit still present so that a future correction changes the test in a visible, reviewed way.

The correct design should mask to the implemented physical-address field rather than merely clearing the page offset.

## 2 MiB large pages

At the PD level, bit 7 selects a 2 MiB page. The implementation uses:

    page = entry AND 0x000fffffffe00000
    offset = va AND ((1 << 21) - 1)

The walker returns after three page-table reads.

Because the physical-base mask is explicit, high attribute bits such as NX are not carried into the physical address for this path.

The contract fixture verifies a 2 MiB mapping and the expected number of entry reads.

## 1 GiB large pages

At the PDPT level, bit 7 selects a 1 GiB page. The implementation uses:

    page = entry AND 0x000fffffc0000000
    offset = va AND ((1 << 30) - 1)

The walker returns after two page-table reads.

The fixture verifies a 1 GiB translation independently.

ChrisCPU does not validate every reserved or alignment bit associated with large-page entries. A complete x86 MMU would reject additional malformed encodings.

## Missing reserved-bit validation

The walker currently focuses on Present, R/W, U/S, A, D, PS and NX. It does not implement comprehensive reserved-bit checks.

Consequences include missing #PF RSVD classification for malformed entries and acceptance of combinations that real hardware would reject.

The page-fault error-code builder does not set bit 3 for reserved-bit violations because no such validation path exists yet.

Physical-address-width checks are also not modeled from CPUID MAXPHYADDR.

## Accessed/Dirty write-back failure

read_pte and write_pte call the machine's physical-memory interface. However, A/D updates deliberately discard the return value from write_pte.

Therefore translation can report success even if the emulator failed to persist the Accessed or Dirty bit in the page table.

The independent MMU fixture forces these writes to fail and records the behavior as a KNOWN GAP.

This is a correctness issue for guests that inspect page-table A/D state. The translation result and the architecturally visible page-table metadata can disagree.

A hardened implementation should propagate or otherwise resolve write-back failure instead of ignoring it.

## Virtual reads

chris_va_read handles an arbitrary byte range by repeatedly:

1. translating the current virtual address;
2. determining the remaining bytes until the next 4 KiB physical boundary;
3. limiting the chunk to the caller's remaining length;
4. reading that chunk with chris_phys_read;
5. advancing until the request is complete.

Zero-length reads return success without translation or physical access.

Using 4 KiB chunks is correct for splitting ordinary crossings, though it is conservative for large-page mappings and can perform more loop iterations than necessary.

## Virtual writes

chris_va_write follows the same structure but always translates with write access and calls chris_phys_write for each chunk.

Zero-length writes are no-ops.

Because translation and physical write happen one chunk at a time, a multi-page write is not transactional.

## Cross-page faults and partial effects

The MMU contract intentionally tests a read beginning two bytes before the end of a mapped page when the following page is absent.

The first two bytes are copied into the caller's buffer, then translation of the second page raises #PF and CR2 points to the second-page address.

A corresponding write test is marked as a known gap: the first two bytes are committed to guest memory before the second page faults. There is no rollback of the first chunk.

This behavior is important for emulator precision. Instruction helpers using chris_va_write can expose partial memory modification from one logical guest access if a later page fails.

A future precise-access layer should preflight all required translations or provide rollback/commit semantics where the architecture requires the instruction to fault without partial visible state.

## Translation outcomes and exception routing

chris_translate uses three failure classes:

| Return | Meaning | Wrapper behavior |
|---:|---|---|
| -1 | guest paging presence/permission failure | set CR2, raise #PF |
| -2 | noncanonical virtual address | raise #GP(0) |
| -3 | physical backing/page-table read unavailable | halt with CHRIS_EXIT_UNMAPPED |

This separation prevents an emulator-internal physical mapping deficiency from being incorrectly reported as a guest page-table fault.

During exception delivery, cpu->delivering suppresses recursive calls to chris_raise. A translation failure is returned to the exception-frame builder, which can escalate through double-fault logic.

## Initial paging installed by chris_boot

chris_boot calls install_tables before starting guest execution.

The boot protocol reserves the final four 4 KiB pages of guest RAM for paging structures and related boot state. install_tables places:

    PML4 at RAM_size - 0x4000
    PDPT at RAM_size - 0x3000
    PD   at RAM_size - 0x2000

PML4[0] points to the PDPT and PDPT[0] points to the PD. RAM is identity-mapped using 2 MiB PDEs with value base OR 0x83, meaning Present, Writable and Page Size.

The number of 2 MiB pages may not exceed 512, so this boot-protocol layout handles at most one PD worth of initial RAM mapping, one GiB.

If a framebuffer exists, install_tables identity-maps its 2 MiB regions into free PDE slots of the same PD.

The initial control state is:

    CR0: PE, NE, WP, PG
    CR3: PML4 physical address
    CR4: PAE
    EFER: LME, LMA
    CPL: 0

User bits are not set in the initial identity mapping. The booted guest therefore starts with supervisor-only mappings.

## No TLB or translation cache

Although ChrisCpu contains a tlb_gen field for broader machine state, the inspected MMU path performs a page-table walk directly on each chris_translate call. There is no translation lookup cache in mmu.c.

This has two consequences.

First, changes to page tables become visible immediately to subsequent translations without explicit INVLPG emulation.

Second, instruction fetch and memory-heavy guests pay repeated physical page-table reads. Performance characteristics therefore differ substantially from hardware and from a TLB-backed emulator.

A future TLB must define invalidation behavior for CR3 writes, INVLPG, global pages, PCID and page-table mutation.

## Unsupported paging features

The current walker does not model:

- five-level paging and CR4.LA57;
- PCID and CR3 no-flush semantics;
- global-page behavior and PGE;
- INVLPG;
- SMEP;
- SMAP;
- protection keys;
- shadow-stack page permissions;
- full PAT/cache-type semantics;
- MAXPHYADDR-dependent reserved bits;
- comprehensive malformed-entry validation;
- TLB caching and invalidation;
- nested/EPT/NPT translation.

Those omissions are compatibility boundaries, especially for modern kernels that probe or enable advanced CR4 features.

## Reproducible MMU evidence

scripts/check_mmu.py compiles the real mmu.c together with tests/source/mmu_contract.c against a synthetic physical-memory backend and a stub exception-delivery function.

The fixture verifies:

- identity translation when paging is disabled;
- a four-level 4 KiB walk;
- Accessed bits at all levels;
- Dirty behavior on writes;
- 48-bit canonical-address rejection;
- user not-present write error code;
- ancestor U/S denial;
- CR0.WP supervisor behavior;
- user write denial with WP clear;
- NX execution denial;
- 2 MiB pages;
- 1 GiB pages;
- distinct unbacked-table result;
- wrapper-generated #PF and CR2;
- wrapper-generated #GP;
- CHRIS_EXIT_UNMAPPED;
- recursive-fault suppression during exception delivery;
- cross-page reads;
- zero-length accesses.

It also deliberately characterizes two known gaps:

- NX leaking into a 4 KiB data physical address;
- ignored Accessed-bit write-back failure.

A third known-gap characterization covers a cross-page write retaining the successfully written first chunk after the second page faults.

The probe is source-bound and reproducible, but its scope is synthetic physical memory. It does not prove guest-OS compatibility, hardware timing or behavior of paging features absent from mmu.c.

## Hardening priorities

The next high-value MMU work is:

1. replace the 4 KiB leaf mask with an explicit physical-address mask that excludes NX and other attribute bits;
2. propagate or correctly handle A/D write-back failures;
3. add reserved-bit and physical-address-width validation with #PF.RSVD;
4. define precise multi-page write semantics and eliminate unintended partial updates;
5. add tests for permission intersections across every page-table level;
6. add malformed 2 MiB and 1 GiB entry tests;
7. implement or explicitly reject unsupported CR4 paging features;
8. introduce a TLB only together with a complete invalidation contract;
9. extend boot mappings beyond the single-PD protocol when larger guest memory is required;
10. add guest-level page-fault handler tests that connect translation, CR2, error code, IDT delivery and IRETQ.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisCPU has a functional four-level long-mode walker with meaningful permission enforcement, large-page support and independently checked A/D behavior. Its strongest current limitations are the incorrect 4 KiB physical-address mask when high attributes are present, ignored A/D write-back failures, absent reserved-bit validation and non-transactional cross-page writes. Those boundaries are explicitly test-characterized rather than hidden behind a generic claim of x86-64 paging support.
