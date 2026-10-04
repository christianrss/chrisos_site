---
id: chrisvm-memory-map
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/boot.c
  - chrisvm/buses/mmio.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - CHRIS_STACK_RSP
  - CHRIS_GDT_PHYS
  - CHRIS_PT_RESERVE
  - CHRIS_FB_PHYS
  - chris_phys_read
  - chris_phys_write
  - install_tables
  - chris_load_elf
depends_on:
  - chrisvm-machine
  - emulator-paging
related:
  - chrisvm-mmio-bus
  - chrisvm-boot
  - physical-memory
  - virtual-memory
---

# ChrisVM physical memory map

## Scope

The ChrisVM physical map is currently defined by a small set of fixed constants plus runtime RAM size and MMIO registrations. There is no central region table describing every physical range. Instead, ownership is distributed across boot constants, RAM allocation, framebuffer state and the MMIO registry.

That makes the map simple enough to inspect directly, but it also creates hidden coupling. The boot loader, page-table builder, framebuffer and physical dispatcher must all agree on addresses without a single authoritative map object validating the complete layout.

This chapter documents the physical-address contract at ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Default layout

With the default 16 MiB RAM configuration, the important fixed physical ranges are:

| Range / address | Role |
|---|---|
| 0x00000000 .. RAM end | guest RAM |
| 0x00070000 .. 0x00070fff | boot-protocol GDT reservation |
| 0x0007f000 .. 0x0007ffff | loader-reserved initial stack page |
| 0x00080000 | initial RSP value, stack grows downward |
| RAM_size - 0x4000 | PML4 page |
| RAM_size - 0x3000 | PDPT page |
| RAM_size - 0x2000 | PD page |
| RAM_size - 0x1000 .. RAM_size | reserved by loader but unused by install_tables |
| 0x02000000 .. 0x0212bfff | linear framebuffer backing bytes |
| arbitrary registered ranges | generic MMIO outside RAM/framebuffer |

Port I/O such as serial 0x3f8..0x3ff and shutdown port 0x501 belongs to a separate address space and is not part of this physical memory map.

## RAM region

ChrisMachine allocates one contiguous zeroed host buffer for guest RAM.

The requested RAM size must be:

- at least 2 MiB;
- aligned to 2 MiB.

The public default is 16 MiB.

The framebuffer placement currently imposes an additional effective ceiling of 32 MiB because chris_fb_attach rejects ram_size values above CHRIS_FB_PHYS.

Thus, for the current machine implementation:

    2 MiB <= RAM <= 32 MiB
    RAM size is a multiple of 2 MiB

The first physical byte after RAM is not automatically treated as a guard page or reserved area. It can become framebuffer or MMIO depending on the chosen address.

## ELF loading is effectively identity-oriented

chris_load_elf accepts 64-bit little-endian x86-64 ELF images.

For each PT_LOAD segment it uses p_vaddr as the destination offset into guest RAM. p_paddr is not used as an independent physical address.

The segment must fit entirely inside RAM.

The loader also rejects higher-half virtual addresses at or above:

    0xffff800000000000

under boot protocol v1.

This produces an identity-oriented early machine model: guest ELF virtual load addresses are copied directly into the same-numbered physical RAM offsets that the initial page tables then identity-map.

It is not yet a general loader for arbitrary virtual-to-physical segment placement.

## Boot-reserved regions inside RAM

The loader rejects PT_LOAD segments that overlap three categories of boot-owned memory.

### GDT page

The fixed GDT physical address is:

    CHRIS_GDT_PHYS = 0x70000

The loader reserves one full 4 KiB page starting at that address.

install_tables currently writes three 8-byte descriptors there:

- null descriptor;
- long-mode code descriptor;
- data descriptor.

Most of the 4 KiB reservation is unused today but protected from ELF loading.

### Initial stack page

The fixed initial stack pointer is:

    CHRIS_STACK_RSP = 0x80000

The loader rejects overlap with the 4 KiB range immediately below it:

    0x7f000 .. 0x7ffff

The stack therefore begins at 0x80000 and grows downward into that reserved page.

The current boot path does not allocate a dynamic stack region. It relies on this convention inside already-zeroed guest RAM.

### Page-table reserve

The loader reserves the final:

    CHRIS_PT_RESERVE = 0x4000

bytes of RAM.

That is four 4 KiB pages.

install_tables currently places only three paging structures:

    PML4 = RAM_size - 0x4000
    PDPT = RAM_size - 0x3000
    PD   = RAM_size - 0x2000

The final page:

    RAM_size - 0x1000 .. RAM_size

is kept out of guest ELF segments but is not used by install_tables in the inspected revision.

This reserved-but-unused page provides some expansion space, but its purpose is not encoded as a distinct structure.

## Initial page-table topology

The boot path constructs a minimal hierarchy:

    PML4[0] -> PDPT
    PDPT[0] -> PD

The PD contains 2 MiB identity mappings for RAM.

For each RAM chunk:

    PDE[i] = physical_base | 0x83

where 0x83 represents Present, Writable and Page Size.

The current layout uses one PD only, so the theoretical initial-map limit is 512 * 2 MiB = 1 GiB.

The machine's fixed framebuffer rule limits RAM much earlier, at 32 MiB.

## Framebuffer physical range

The framebuffer begins at:

    CHRIS_FB_PHYS = 0x02000000

or 32 MiB.

Its dimensions are:

    width  = 640
    height = 480
    pitch  = 640 * 4

The backing size is:

    640 * 480 * 4 = 1,228,800 bytes = 0x12c000

Therefore its byte range is:

    0x02000000 .. 0x0212bfff

with the first address after the framebuffer at:

    0x0212c000

The backing storage is not part of the RAM allocation. It is a separate host buffer owned by ChrisFb.

## Framebuffer virtual mapping

install_tables identity-maps the framebuffer into the same virtual address range.

It aligns the beginning downward to a 2 MiB boundary and installs 2 MiB PDEs until the entire framebuffer size is covered.

Since 0x02000000 is already 2 MiB aligned and the framebuffer occupies less than 2 MiB, one large page covers:

    0x02000000 .. 0x021fffff

Only the first 0x12c000 bytes correspond to framebuffer backing. Physical accesses to the remaining addresses of that 2 MiB virtual mapping do not automatically belong to framebuffer memory.

If no generic MMIO region exists there, such accesses fail at the physical dispatcher.

This distinction between page-table coverage and device backing is important.

## Why RAM cannot exceed 32 MiB today

For ram_size exactly 32 MiB, RAM occupies:

    0x00000000 .. 0x01ffffff

and the framebuffer begins immediately afterward at 0x02000000.

That layout is valid.

If RAM were larger than 32 MiB, it would overlap the fixed framebuffer base.

Rather than relocating the framebuffer, chris_fb_attach rejects machine creation.

The limit is therefore a memory-map collision policy encoded indirectly in the framebuffer device.

A future machine map should detect and resolve regions centrally instead of allowing one device constructor to define the maximum guest RAM size.

## Generic MMIO regions

Generic MMIO can be registered at runtime using chris_mmio_map.

Each region supplies:

- base;
- size;
- read callback;
- write callback;
- context pointer.

Up to eight regions can exist.

The registration function does not test for overlap with:

- RAM;
- framebuffer;
- another MMIO slot.

This means the stored registry may contain a region that can never be reached because a higher-precedence region owns the same physical address.

## Physical dispatch precedence

chris_phys_read and chris_phys_write apply this precedence:

    1. RAM
    2. framebuffer
    3. generic MMIO

The first two checks require the complete access to fit inside the corresponding region.

Generic MMIO is used only after both fast paths fail.

Therefore the effective map is not simply the set of registered ranges. It is the registered ranges filtered by dispatcher precedence.

### RAM shadows MMIO

If generic MMIO overlaps RAM, a request wholly contained in RAM is always served by RAM.

The MMIO callback is not reached.

### Framebuffer shadows MMIO

If generic MMIO overlaps the framebuffer and the request fits completely in framebuffer backing, framebuffer wins.

### MMIO only owns remaining addresses

Generic MMIO is effectively a fallback physical region class.

This behavior should be documented as part of the platform contract until overlap is rejected explicitly.

## Mixed-region requests are not split

A request spanning two region types can fail even when each byte is individually backed.

For example:

    [last 2 RAM bytes][first 2 MMIO bytes]

as one 4-byte physical request.

The RAM fast path rejects the request because all four bytes do not fit in RAM.

The generic MMIO loop then starts at the original address and tries to resolve even the first two RAM bytes as MMIO.

If no MMIO mapping covers them, the request fails.

There is no region-boundary splitter.

The same design issue can occur at framebuffer boundaries.

A mature physical map should decompose requests into region-owned subranges or reject unsupported cross-region accesses in a deliberate, architecture-aware way.

## MMIO transaction width is lost

Generic MMIO access is processed one byte at a time.

A 4-byte guest transaction produces four callback calls with:

    size = 1

rather than one callback with size 4.

Therefore the physical map currently preserves byte values but not transaction width.

That matters for registers whose behavior depends on byte/word/dword/qword access width.

Future device work needs a dispatcher that identifies the owning region first, then sends the largest valid transaction to that device.

## Unmapped physical memory

If an address lies outside RAM, framebuffer and registered MMIO, chris_phys_read/chris_phys_write return failure.

When the virtual-memory wrapper encounters this after a valid guest page-table translation, ChrisCPU classifies it as:

    CHRIS_EXIT_UNMAPPED

rather than generating a normal guest #PF.

That is deliberate. The page tables may be valid, while the emulator has no machine resource backing the translated physical address.

This separates guest paging faults from missing virtual-hardware implementation.

## Test MMIO at 96 MiB

test_chrisvm.c demonstrates a generic MMIO device at:

    0x06000000

or 96 MiB.

The test manually installs a 2 MiB PDE that maps the virtual address to that physical region, then runs guest code that writes and reads the mapped cell.

This is important evidence that generic MMIO does not need to sit below the 32 MiB framebuffer or inside RAM.

The page-table mapping and physical backing are separate concerns.

## Loader collision checks are incomplete by design

chris_load_elf explicitly rejects overlap with:

- final 16 KiB page-table reserve;
- GDT page;
- stack page.

It does not inspect the runtime MMIO registry.

It also does not need to reject framebuffer overlap directly because PT_LOAD segments must already fit inside RAM, and framebuffer starts at or above the RAM ceiling.

A future configurable memory map will need a generic region-collision API rather than a hard-coded list of boot constants.

## Physical versus virtual addresses

The current boot protocol identity-maps RAM and framebuffer, but ChrisVM still maintains a conceptual distinction.

The MMU translates:

    guest virtual address -> guest physical address

Then the machine dispatcher resolves:

    guest physical address -> RAM / framebuffer / MMIO / unmapped

The two stages must remain separate.

The fact that many initial addresses are numerically identical is a property of boot protocol v1, not a reason to collapse the two models.

This separation is required for later higher-half kernels, user address spaces, shared mappings and device remapping.

## GDT placement and virtual access

The GDT is stored in physical RAM at 0x70000.

Because RAM is identity-mapped during boot, GDTR.base is also set to 0x70000 and descriptor reads through guest virtual memory reach the same backing bytes.

This again depends on the initial identity mapping.

A future non-identity boot path can keep the GDT at one physical address while exposing it through a different virtual mapping, provided GDTR contains the virtual linear address expected by the CPU model.

## Stack placement and growth

RSP begins at 0x80000 by default.

The reserved loader range is only one 4 KiB page below it.

The emulator does not enforce a dedicated stack-region limit. If guest code pushes beyond that page into lower mapped RAM, the MMU can continue to permit accesses as long as page tables allow them.

Thus the "stack page" is a loader ownership reservation, not a guard-enforced stack object.

A true guard page would require a not-present or protected mapping below the intended stack.

## Reserved page-table memory and guest access

The final 16 KiB of RAM are excluded from ELF load segments, but they remain ordinary physical RAM after boot.

The initial identity map includes those physical addresses because RAM is mapped in 2 MiB chunks.

Guest code can therefore access or overwrite its own page tables through the identity mapping.

That is normal for privileged kernel code, but it means "reserved from loader" does not mean "protected from guest execution."

Protection would require page-table permissions or a separate ownership policy.

## No central region descriptor

ChrisMachine does not currently have a generic structure such as:

    region {
        base
        size
        type
        owner
        permissions
        access widths
        priority
    }

Instead, the map is inferred from:

- ram_size;
- framebuffer constants;
- MMIO slots;
- boot constants;
- dispatcher ordering.

This makes simple code possible, but complicates validation, visualization, snapshots and future hotplug.

A central region model would allow ChrisVM to generate its own authoritative map and reject collisions before execution.

## Relationship to boot protocol v1

Boot protocol v1 assumes:

- guest ELF inside low RAM;
- identity-mapped RAM;
- fixed low GDT;
- fixed low stack;
- paging structures at top of RAM;
- fixed framebuffer at 32 MiB;
- no firmware-created map;
- no ACPI/e820-style discovery protocol.

The guest therefore receives a machine by convention, not by enumerating a firmware memory map.

This is sufficient for the current standalone ChrisVM guests but not yet enough to boot arbitrary operating systems expecting firmware memory discovery.

## Current validation evidence

The repository tests verify:

- ELF segments cannot overlap boot-reserved regions;
- default boot creates functioning page tables;
- MMIO at 96 MiB can be mapped and accessed;
- framebuffer writes reach the fixed framebuffer backing;
- missing physical backing causes CHRIS_EXIT_UNMAPPED;
- page-table and paging permission behavior is checked independently by the MMU contract fixture.

These tests establish key map behavior but do not exhaustively test region collisions or every boundary crossing.

## Hardening priorities

The highest-value next steps are:

1. introduce one authoritative physical-region registry for RAM, framebuffer and MMIO;
2. detect overlap at registration/construction time;
3. remove the framebuffer-imposed RAM ceiling through relocatable device placement;
4. split physical requests safely at region boundaries;
5. preserve guest access width in MMIO dispatch;
6. express boot-reserved regions through the same map rather than hard-coded ELF checks;
7. define a real firmware/boot memory-map handoff for guests;
8. add guard-page semantics for the initial stack if that protection is desired;
9. classify the fourth reserved top-of-RAM page explicitly or release it;
10. add boundary tests for RAM end, framebuffer end and adjacent MMIO regions;
11. distinguish region permissions from page-table permissions;
12. expose the generated physical map to debugger/documentation tooling.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, the ChrisVM physical map is intentionally simple: low contiguous RAM, fixed boot structures inside RAM, a fixed framebuffer at 32 MiB and a small fallback MMIO registry. The design is sufficient for current ChrisCPU smoke guests, but it lacks one authoritative region model. The most important consequences are the 32 MiB RAM ceiling, implicit dispatch priority, unvalidated overlaps and inability to split one physical request across region boundaries.
