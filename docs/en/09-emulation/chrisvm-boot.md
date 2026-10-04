---
id: chrisvm-boot
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/chrisvm.h
  - chrisvm/machine/boot.c
  - chrisvm/machine/machine.c
  - chrisvm/frontend/main.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - CHRIS_BOOT_PROTOCOL
  - chris_load_elf
  - chris_boot
  - install_tables
depends_on:
  - chrisvm-devices
  - chris-architecture-state
  - emulator-paging
  - elf-linking
related:
  - chrisvm-memory-map
  - chrisvm-debugger
  - boot-information
  - higher-half-kernel
---

# ChrisVM boot protocol v1

## Scope

ChrisVM boot protocol v1 is a synthetic execution handoff for small x86-64 ELF guests. It is not a firmware emulator and it does not reproduce the physical CPU transition from reset through real mode, protected mode and long mode.

The protocol performs three high-level operations:

1. load accepted ELF PT_LOAD segments into low guest RAM;
2. construct a minimal long-mode memory/segment environment;
3. place the CPU directly at the selected 64-bit entry point with a predefined stack.

This makes ChrisVM useful as an execution harness for controlled guests while keeping BIOS, UEFI, Limine and the full ChrisOS higher-half kernel outside the claimed compatibility boundary.

The public constant:

    CHRIS_BOOT_PROTOCOL = 1

names the current protocol version, but the inspected source does not serialize or hand that version to the guest through a boot-information structure.

This chapter documents ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Frontend lifecycle

The command-line frontend performs:

    configuration
    -> read ELF file into host memory
    -> create ChrisMachine
    -> install host log/serial callbacks
    -> chris_load_elf
    -> chris_boot
    -> chris_run or debug loop
    -> optional framebuffer dump/view
    -> destroy machine

Loading and boot are separate operations.

That separation is useful because ELF validation/copying and CPU-state construction are distinct contracts.

## Accepted ELF envelope

chris_load_elf requires:

- non-null machine and image;
- enough bytes for Elf64Ehdr;
- ELF magic;
- class ELFCLASS64;
- little-endian encoding;
- e_machine equal to 62, x86-64;
- program-header entry size equal to the local Elf64Phdr structure size;
- at least one program header;
- complete program-header table inside the input image.

Only PT_LOAD program headers are copied.

Other program-header types are ignored.

## What the loader does not validate

The current loader does not use several ELF fields as semantic gates.

The inspected implementation does not validate or act on:

- e_type;
- e_version beyond the bytes implicitly copied into the header;
- p_flags;
- p_paddr;
- p_align;
- section headers;
- relocations;
- dynamic linking metadata.

Therefore "accepted ELF" means compatible with this narrow loader contract, not generally valid under every ELF ABI rule.

## p_vaddr is the load destination

For each PT_LOAD segment, the loader copies bytes to:

    machine RAM + p_vaddr

The segment's p_paddr is ignored.

This makes boot protocol v1 effectively identity-oriented: the ELF virtual address is also used as the physical RAM offset.

The initial page tables later identity-map RAM, so the same numeric guest virtual address reaches those bytes.

This is intentionally simpler than a loader that distinguishes file virtual layout from physical placement.

## Higher-half images are rejected

A PT_LOAD segment whose p_vaddr is at or above:

    0xffff800000000000

is rejected with:

    "higher-half ELF is outside boot protocol v1"

The ELF entry point is subject to the same higher-half boundary.

This deliberately excludes the normal higher-half ChrisOS kernel image from protocol v1.

The source does not special-case kstart or silently relocate the production kernel.

That is an important compatibility boundary: ChrisVM v1 boots dedicated low-memory guests, not the normal Limine kernel path.

## Segment bounds

For a PT_LOAD segment, the loader validates:

    p_memsz >= p_filesz

and verifies the file range is inside the supplied image.

It also requires the in-memory segment to fit fully inside guest RAM.

The subtraction-style RAM check avoids unsigned end-address overflow:

    p_memsz <= ram_size - p_vaddr

after first proving p_vaddr < ram_size.

## BSS-style zero filling

After copying p_filesz bytes, when:

    p_memsz > p_filesz

the remaining memory is zeroed.

This implements the standard loadable-segment expectation for zero-initialized memory beyond file content.

Because machine RAM itself starts zeroed, the explicit memset still matters after arbitrary prior machine writes or overlapping load operations.

## Reserved boot-memory collision checks

Each PT_LOAD segment is rejected if it overlaps:

- the final CHRIS_PT_RESERVE bytes of RAM;
- the fixed GDT page at CHRIS_GDT_PHYS;
- the 4 KiB page immediately below CHRIS_STACK_RSP.

These regions belong to protocol v1 rather than the loaded ELF.

The checks are hard-coded rather than derived from a central machine-region registry.

## Segment overlap with other PT_LOAD segments

The current loader does not reject overlap between PT_LOAD segments themselves.

Segments are processed in program-header order.

A later segment can therefore overwrite bytes copied or zeroed by an earlier segment.

For controlled linker output this may never occur, but the loader does not enforce non-overlap as an invariant.

## Partial load on late failure

ELF loading is not transactional.

Suppose early PT_LOAD segments are copied successfully and a later segment fails validation.

chris_load_elf returns failure, but already-copied RAM bytes are not rolled back.

Machine state can therefore contain a partial failed image.

The frontend destroys the machine immediately on boot failure, so the ordinary command-line path does not reuse that state.

The library API itself, however, does not guarantee rollback.

## Entry-point validation

After processing program headers, the loader requires the entry point to be:

- below the protocol-v1 higher-half boundary;
- below ram_size.

It then stores:

    machine->entry = e_entry

The loader does not verify that the entry point:

- lies inside a PT_LOAD segment;
- lies inside a segment marked executable;
- points to bytes initialized by the loader.

Since p_flags is ignored, executable permission is not part of the loader contract.

A malformed-but-in-range entry can therefore be accepted and fail later during execution.

## No ELF relocation

The image is copied exactly at p_vaddr.

There is no load bias or relocation stage.

Position-independent executables are not dynamically relocated, and relocation records are not processed.

Guests must already be linked for addresses compatible with protocol v1.

## chris_boot entry selection

chris_boot accepts an explicit entry argument.

If entry is zero, it uses:

    machine->entry

set by chris_load_elf.

The final entry must be nonzero and below ram_size.

Passing an explicit nonzero entry allows host code to override the ELF header's stored entry, but it remains constrained to low RAM.

## RAM requirements

Boot requires RAM to be:

- at least 2 MiB;
- a multiple of 2 MiB.

The machine layer already applies the same basic alignment requirement.

The current framebuffer placement limits normally created machines to at most 32 MiB, despite install_tables being structurally capable of mapping more.

## Reset before boot state

chris_boot begins with:

    chris_arch_reset(&st)

which zeros the architectural record, sets RFLAGS bit 1 and establishes the project reset CR0 baseline.

It then builds a synthetic long-mode state.

This is not instruction-by-instruction transition from x86 reset.

## Page-table construction

Protocol v1 reserves the final four pages of guest RAM.

install_tables places:

    PML4 = RAM_size - 0x4000
    PDPT = RAM_size - 0x3000
    PD   = RAM_size - 0x2000

It clears 0x3000 bytes beginning at PML4, which initializes those three pages.

PML4[0] points to PDPT.

PDPT[0] points to PD.

RAM is mapped with 2 MiB PDEs.

## Initial RAM mapping

For each 2 MiB RAM chunk:

    PDE[i] = physical_base | 0x83

The flags represent:

- Present;
- Writable;
- Page Size.

The mapping is identity:

    virtual address == physical address

for initial RAM.

No User bit is set.

The guest begins with supervisor mappings.

## One-PD page-table limit

pages is calculated as:

    ram_size / 2 MiB

and rejected when it exceeds 512.

Thus this table topology can represent at most 1 GiB of RAM through PDPT[0].

The current machine's framebuffer limit reaches first, but the protocol itself has this separate one-PD ceiling.

## Framebuffer mapping

If framebuffer backing exists, install_tables identity-maps its 2 MiB-aligned coverage using PDEs in the same PD.

Before writing a framebuffer PDE, it checks the target slot is zero.

This prevents the framebuffer mapping from silently replacing a RAM mapping.

With the current machine layout, framebuffer begins exactly after the maximum allowed 32 MiB RAM, so collision is normally avoided.

## Fixed GDT

The protocol writes three descriptors at:

    CHRIS_GDT_PHYS = 0x70000

The descriptors are:

- null;
- 64-bit code;
- data.

GDTR is configured to reference those 24 bytes.

The loader reserves the entire 4 KiB page against ELF segments even though only a small prefix is used.

## Initial segment state

The boot state sets:

    CS selector = 0x08
    SS selector = 0x10
    DS = SS
    ES = SS

CS receives base zero, limit 0xffffffff and the stored long-mode attributes.

FS and GS remain at reset-zero state.

TR and LDTR also remain zero.

There is no TSS installed by protocol v1.

## Control state

install_tables sets:

    CR0 = PE | NE | WP | PG
    CR3 = PML4 physical address
    CR4 = PAE
    EFER = LME | LMA

This places the architecture record directly into the state expected for 64-bit paged execution.

The emulator does not execute the real transition sequence required by hardware to enter long mode.

In particular, no firmware code writes those registers instruction by instruction.

## Long-mode state is asserted, not transitioned

On physical x86 hardware, LMA is not simply a software-selected independent state bit.

Protocol v1 uses ChrisArchitectureState as a synthetic starting contract and directly establishes LME/LMA together with paging state.

This is appropriate for a VM execution harness, but should not be described as emulating processor startup.

The canonical documentation elsewhere covers actual reset/firmware/boot transitions.

## Initial privilege

The protocol sets:

    CPL = 0

The guest starts as supervisor/kernel code.

There is no ring transition during boot.

No user-mode context is created.

## RFLAGS

RFLAGS is explicitly set to:

    2

The Interrupt Flag begins clear.

Therefore external IRQ delivery requiring IF does not occur until guest code enables it.

No legacy firmware flag state is inherited.

## Initial stack

The default initial stack pointer is:

    CHRIS_STACK_RSP = 0x80000

unless the host passes a nonzero rsp argument to chris_boot.

The loader protects the 4 KiB page immediately below the default stack address from ELF loading.

The stack grows downward.

There is no guard mapping beneath it and no stack metadata handed to the guest.

## Backend handoff

After page tables, GDT and register state are prepared, chris_boot calls:

    backend->set_state(cpu, &st)

Then it marks:

    machine->booted = 1
    machine->entry = entry

This keeps boot construction backend-neutral in principle.

ChrisCPU copies the complete structure.

ChrisHV remains nonfunctional in the inspected revision.

## No IDT installed

Protocol v1 does not create an IDT or configure IDTR.

IDTR remains reset-zero unless guest code installs one.

As documented by the exception model, a fault while IDTR remains zero is reported to the ChrisVM monitor as CHRIS_EXIT_EXCEPTION rather than delivered to a guest handler.

This makes early guest failures easy to diagnose but differs from a complete firmware/OS startup environment.

## No TSS

The boot protocol does not build a TSS or load TR.

Consequences include missing:

- IST stacks;
- privilege-transition stack switching;
- TSS I/O bitmap.

Current low-level guests therefore run in a simplified ring-0 environment.

## No boot-information structure

The inspected protocol does not build or pass a structured boot-information object containing:

- RAM map;
- framebuffer descriptor;
- module list;
- command line;
- firmware tables;
- ACPI pointers;
- CPU topology;
- protocol version.

The guest is expected to know the current ChrisVM v1 constants or use a purpose-built test contract.

CHRIS_BOOT_PROTOCOL exists as a host/source constant but is not visibly delivered to the guest through a register or memory record.

## No BIOS, UEFI or Limine

ChrisVM v1 does not emulate:

- BIOS reset services;
- UEFI firmware;
- UEFI memory map;
- PE/COFF loader;
- Limine protocol requests/responses;
- bootloader modules;
- firmware graphics setup.

The production ChrisOS boot path remains QEMU/real-machine firmware plus Limine.

ChrisVM v1 is a separate synthetic loader.

## Difference from the real ChrisOS kernel boot

The repository's normal ChrisOS kernel is higher-half and uses the Limine path.

The ChrisVM loader explicitly rejects such higher-half PT_LOAD addresses.

Therefore successful boot of current ChrisVM test guests is not evidence that ChrisVM can boot the production ChrisOS image.

Replacing QEMU for the real kernel requires either:

- a richer ChrisVM boot protocol that constructs the kernel's expected handoff;
- a Limine-compatible loader path;
- or firmware/bootloader execution.

That remains future work.

## No NX by default

EFER.NXE is not set by install_tables.

Initial PDEs also do not distinguish executable/data memory.

The guest can enable NXE and modify page tables later where supported by the MMU.

Protocol v1 itself starts with broad executable supervisor identity mappings.

## No per-segment ELF permissions in paging

p_flags is ignored.

Therefore ELF PF_R/PF_W/PF_X permissions are not translated into initial page-table permissions.

All initial RAM mappings are writable supervisor large pages, and execution is allowed while NXE is inactive.

This is a significant simplification compared with a loader that enforces ELF segment protection.

## Frontend failure behavior

If chris_load_elf or chris_boot fails, the command-line frontend:

- prints a boot error;
- destroys the machine;
- frees the input buffer;
- exits with status 2.

The error text comes from chris_load_elf where available.

chris_boot itself returns only success/failure and does not fill a detailed error string.

Consequently, state-construction failures such as table collision can produce the generic frontend text "entry" when no loader error exists.

Boot diagnostics should eventually become more structured.

## Current test evidence

test_chrisvm.c verifies:

- valid ELF guest load and boot;
- guest entry execution to HLT;
- guest serial output;
- bad ELF magic rejection;
- truncated ELF rejection;
- higher-level machine execution;
- framebuffer splash guest;
- low-level fault behavior after boot.

The test suite also directly boots raw byte arrays at low RAM addresses without ELF when convenient.

This provides strong evidence for the controlled protocol-v1 workflow, not for firmware compatibility.

## Loader-validation gaps

High-value missing validation includes:

- e_type policy;
- ELF header version policy;
- at least one PT_LOAD requirement;
- PT_LOAD overlap detection;
- entry belonging to a loaded executable segment;
- p_align consistency;
- p_flags-to-page-permission handling;
- explicit p_paddr policy;
- rollback after partial load failure.

These should be specified before the loader accepts less-controlled guest binaries.

## Boot-state hardening priorities

The next boot-layer work is:

1. define a guest-visible versioned boot-information structure;
2. make memory map and framebuffer discovery explicit;
3. support the actual ChrisOS higher-half image or clearly define a separate ChrisVM guest ABI;
4. decide whether to emulate Limine, reproduce its handoff or retain a native ChrisVM protocol;
5. validate ELF entry/segments more rigorously;
6. translate ELF permissions into page permissions where appropriate;
7. make ELF loading transactional or reset RAM on failure;
8. provide structured errors from chris_boot;
9. install or explicitly delegate IDT/TSS initialization;
10. define NX and security state at boot;
11. move fixed boot addresses into the authoritative machine map;
12. add end-to-end tests for protocol-version handoff and higher-half evolution.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisVM boot protocol v1 is a deliberately synthetic low-memory x86-64 handoff. It validates and copies a narrow ELF subset, identity-maps RAM and framebuffer, installs a minimal GDT and directly initializes long-mode architectural state. It does not execute firmware, Limine or the real long-mode transition and it intentionally rejects the production higher-half ChrisOS ELF path. That distinction is fundamental when interpreting current ChrisVM boot evidence.
