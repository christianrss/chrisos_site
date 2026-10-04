---
id: chrisvm-boot-spec
lang: en
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/boot.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/guests/link.ld
  - chrisvm/guests/arith.asm
  - chrisvm/guests/splash.asm
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_load_elf
  - chris_boot
  - chris_arch_reset
depends_on:
  - chrisvm-spec
  - chrisvm-boot
  - elf-linking
  - x86-64-memory-privilege
related:
  - higher-half-kernel
  - linker-script
  - reset-firmware
  - limine
---

# ChrisVM boot protocol v1

## Scope

ChrisVM boot protocol version 1 is a **direct ELF boot contract**.

It does not emulate BIOS, UEFI, Limine or the x86 reset vector.

The host loads an ELF64 guest directly into guest RAM, constructs minimal x86-64 long-mode state, creates identity page tables and starts the guest at the ELF entry point.

The protocol version constant is:

    CHRIS_BOOT_PROTOCOL = 1

This specification describes the exact contract implemented at ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Boot sequence

The normal host-side sequence is:

    chris_config_init()
    chris_machine_create()
    chris_load_elf()
    chris_boot()
    chris_run()

The command-line frontend passes entry `0` to `chris_boot`.

In that case the boot routine uses the ELF entry previously stored by `chris_load_elf`.

The default stack pointer passed by the frontend is:

    CHRIS_STACK_RSP = 0x0000000000080000

## Design intent

Protocol v1 is intentionally simple.

It exists to validate:

- ChrisCPU execution;
- ELF loading;
- long-mode paging;
- stack/control flow;
- serial output;
- framebuffer output;
- exceptions and memory behavior.

It deliberately skips firmware discovery.

That keeps the first machine contract small enough to test independently of a full PC platform.

## Required ELF class

The loader accepts only:

    ELF class:      ELF64
    endianness:     little-endian
    machine:        EM_X86_64 (62)

The ELF header must contain at least one program header.

The program-header entry size must equal the loader's `Elf64Phdr` structure size.

The program-header table must fit completely inside the input image.

## ELF type and section-table policy

The current loader is program-header driven.

It does not use ELF section headers for loading.

It also does not currently reject based on `e_type`.

Therefore the normative loading contract is determined by valid PT_LOAD program headers and the entry address, not by section-table content or a strict ET_EXEC/ET_DYN check.

Guests should nevertheless be linked as simple executable images rather than relying on unspecified ELF-type behavior.

## PT_LOAD handling

Only program headers with:

    p_type == PT_LOAD

are copied.

Other program-header types are skipped.

For each PT_LOAD segment, the loader requires:

[
p_memsz ge p_filesz
]

and verifies that the file range:

[
[p_offset, p_offset+p_filesz)
]

is fully contained in the host ELF buffer.

## Destination address

Protocol v1 loads each PT_LOAD segment at:

    guest physical/linear destination = p_vaddr

`p_paddr` is not used.

This is a defining property of the protocol.

Because initial paging is identity-mapped, the same numeric address is both the guest virtual address and the RAM physical address for ordinary loaded code/data.

## BSS zeroing

If:

[
p_memsz > p_filesz
]

the bytes after the file data up to `p_memsz` are zero-filled.

Thus ordinary ELF BSS semantics are provided.

## Lower-half restriction

Protocol v1 rejects any PT_LOAD segment whose `p_vaddr` is at or above:

    0xffff800000000000

The loader returns the explicit error:

    higher-half ELF is outside boot protocol v1

The ELF entry point is subject to the same higher-half restriction.

Therefore protocol v1 is a **lower-half direct-boot protocol**.

## RAM bounds

Every loadable segment must fit entirely inside guest RAM:

[
p_vaddr < ram_size
]

and:

[
p_memsz le ram_size - p_vaddr
]

The ELF entry must also be below `ram_size`.

This prevents PT_LOAD data from being copied directly into framebuffer or MMIO ranges during load.

## Reserved boot memory

Protocol v1 reserves several RAM regions before guest execution.

### GDT page

    0x00070000 .. 0x00070fff

The loader rejects PT_LOAD segments overlapping this 4 KiB page.

### Initial stack page

    0x0007f000 .. 0x0007ffff

The initial stack pointer is:

    0x00080000

and the stack grows downward into the reserved page.

The loader rejects segments overlapping that page.

### Page-table reserve

The final 16 KiB of guest RAM are reserved:

    [ram_size - 0x4000, ram_size)

PT_LOAD segments may not overlap this region.

## Page-table placement

Within the final 16 KiB reserve, protocol v1 currently uses:

    PML4 = ram_size - 0x4000
    PDPT = ram_size - 0x3000
    PD   = ram_size - 0x2000

The final page at:

    ram_size - 0x1000

remains inside the reserved protocol range but is not used by the current `install_tables` routine.

Guests must treat the full 16 KiB as reserved.

## RAM-size alignment

The machine and boot protocol require guest RAM to be:

- at least 2 MiB;
- aligned to 2 MiB.

Formally:

[
ram_size ge 2MiB
]

and:

[
ram_size mod 2MiB = 0
]

The default is 16 MiB.

The fixed framebuffer topology constrains the current machine to no more than 32 MiB RAM.

## Initial identity mapping

The boot routine identity-maps all guest RAM using 2 MiB pages.

For RAM page index (i):

[
VA = PA = i cdot 2MiB
]

Each PD entry is written with value:

    physical_base | 0x83

The relevant low bits are:

- Present;
- Read/Write;
- Page Size.

Thus the initial RAM mapping is supervisor-writable and uses 2 MiB pages.

## Initial page-table hierarchy

The initial hierarchy uses one PML4 entry, one PDPT entry and one PD:

    PML4[0] -> PDPT
    PDPT[0] -> PD
    PD[i]   -> 2 MiB identity page

This covers the low canonical address region needed by current guests.

The implementation permits at most 512 PD entries in this setup.

The current RAM constraints are far below that ceiling.

## Framebuffer mapping

The framebuffer physical base is:

    0x02000000

Its geometry is:

    640 x 480
    32 bits/pixel
    pitch 2560 bytes

If the framebuffer exists, the boot routine maps the physical range using 2 MiB PDEs in the same page directory.

The mapping is identity-based:

    framebuffer virtual address == framebuffer physical address

The current framebuffer occupies less than one 2 MiB page, but the algorithm maps all required 2 MiB chunks for the declared framebuffer size.

## Framebuffer collision rule

When adding a framebuffer PDE, `install_tables` requires the corresponding PD slot to be zero.

If RAM identity mapping already occupies the same slot, boot fails.

The machine prevents the ordinary collision by rejecting RAM that extends above the framebuffer base.

This is why the fixed 32 MiB framebuffer address affects allowed RAM size.

## GDT contents

The protocol installs three 8-byte descriptors at:

    0x00070000

The entries are:

    GDT[0] = null
    GDT[1] = 64-bit code descriptor
    GDT[2] = data descriptor

The current raw values are:

    0x0000000000000000
    0x00af9a000000ffff
    0x00cf92000000ffff

The GDTR limit is:

    sizeof(descriptors) - 1

or 23 bytes.

## Segment selectors

The initial selectors are:

    CS = 0x08
    SS = 0x10

DS and ES are initialized from the same data-segment state as SS.

The code-segment base is zero.

The initial CPL is:

    0

Protocol v1 therefore starts the guest directly in kernel privilege.

## Initial CR0

The initial CR0 bits set by the boot protocol are:

    PE
    NE
    WP
    PG

Conceptually:

[
CR0 = PE | NE | WP | PG
]

This means protected mode and paging are already active.

The guest does not execute the historical transition from real mode to protected/long mode.

## Initial CR3

CR3 points to:

    ram_size - 0x4000

which is the protocol-created PML4.

The guest may later replace CR3 and construct its own mappings, subject to the subset of paging behavior supported by ChrisCPU.

## Initial CR4

The initial CR4 contains:

    PAE

This is required for x86-64 paging.

Other CR4 facilities are not enabled by the protocol.

## Initial EFER

The initial EFER contains:

    LME
    LMA

Long mode is therefore already active.

NXE is not enabled by default.

SCE is not enabled as a boot facility.

The boot protocol is not a firmware transition environment; it provides the guest with a ready long-mode CPU.

## Initial RFLAGS

The initial RFLAGS value is:

    0x2

The architecturally fixed bit 1 is set.

Interrupt Flag is not initially set.

A guest that wants interrupt delivery must configure the required state and enable interrupts itself.

The current machine does not provide a complete PC interrupt platform.

## Initial RIP

If the caller supplies nonzero `entry`, that value becomes RIP.

If the caller supplies zero, the stored ELF entry is used.

After resolution the entry must be:

- nonzero;
- below `ram_size`.

Boot otherwise fails.

## Initial RSP

If the caller provides nonzero `rsp`, it is used.

If zero is passed, ChrisVM uses:

    0x80000

The standard frontend passes `0x80000` explicitly.

The protocol reserves only the immediately lower 4 KiB stack page during ELF-load overlap validation.

A guest that needs a larger stack is responsible for reserving/using RAM accordingly.

## Other registers

`chris_boot` begins from `chris_arch_reset`, which zeroes the architecture state before installing boot state.

Therefore general-purpose registers other than RSP begin zero unless later set by boot setup.

Control/segment fields not explicitly initialized remain at their reset/default values.

Guests should not infer firmware-style register conventions beyond the fields specified here.

## IDT state

Protocol v1 does not install an IDT.

IDTR therefore remains zero after the architecture reset unless changed by guest code.

An exception before the guest installs an IDT is reported to the monitor as:

    CHRIS_EXIT_EXCEPTION

rather than being delivered through a guest handler.

This behavior is intentional and heavily used by the test suite.

## TSS and privilege-transition state

Protocol v1 does not create a TSS or configure a user-mode transition path.

It starts at CPL0.

Guests that want rings, TSS-based stack switching or more complete interrupt privilege transitions must construct that state themselves, within the subset supported by ChrisCPU.

## Firmware services

The following do not exist in protocol v1:

- BIOS interrupts;
- UEFI boot services;
- UEFI runtime services;
- ACPI discovery;
- SMBIOS;
- Limine requests/responses;
- multiboot structures;
- firmware memory map;
- PCI firmware enumeration.

A guest depending on those services is not protocol-v1 compatible.

## Device state available at entry

Before guest entry, machine creation has attached:

- serial port at `0x3f8..0x3ff`;
- ChrisVM shutdown port at `0x501`;
- linear framebuffer at `0x02000000`.

There is no disk device in the baseline boot protocol.

The guest image is already in RAM because the host loader placed it there.

## Serial boot contract

The serial device behaves sufficiently like the current 16550 subset for guest output and loopback tests.

A guest may write characters to:

    0x3f8

subject to the emulated line-control/divisor-latch behavior.

The arithmetic guest uses this channel to emit:

    OK

before halting.

## Shutdown ABI

A guest can request monitor shutdown by writing a value whose low byte is `1` to:

    0x501

The machine then exits with:

    CHRIS_EXIT_SHUTDOWN

This is a ChrisVM protocol device, not a standard x86 firmware interface.

## Example linker contract

The bundled direct-boot guests use:

    OUTPUT_FORMAT(elf64-x86-64)
    ENTRY(_start)

and place code starting at:

    0x1000

The linker creates a PT_LOAD text segment.

This layout stays well below reserved boot regions and is identity-addressable immediately at entry.

## Arithmetic guest

The reference arithmetic guest demonstrates the minimum direct-boot execution path.

It:

1. writes `OK\n` to COM1;
2. performs integer arithmetic;
3. performs a RAM round trip at `0x4000`;
4. exercises CALL/RET;
5. halts.

The test requires:

- `CHRIS_EXIT_HLT`;
- RAX result 31;
- serial output exactly `OK\n`.

This is executable evidence for the boot contract.

## Splash guest

The splash guest writes directly to:

    0x02000000

using a 640x480 32-bit framebuffer model.

It exercises REP STOS and ordinary memory writes through the identity-mapped framebuffer.

It emits:

    splash

over serial and then halts.

Tests validate both serial text and selected framebuffer pixels.

## ELF rejection cases

The loader rejects, among other conditions:

- missing/truncated ELF header;
- bad ELF magic;
- non-64-bit class;
- non-little-endian encoding;
- machine other than x86-64;
- missing program headers;
- wrong program-header entry size;
- program-header table out of input range;
- PT_LOAD file range outside input;
- `p_memsz < p_filesz`;
- segment outside guest RAM;
- higher-half segment;
- overlap with GDT page;
- overlap with initial stack page;
- overlap with final 16 KiB protocol reserve;
- higher-half or out-of-RAM entry.

These are host-loader failures, not guest CPU exceptions.

## Segment flags

The current loader does not convert PT_LOAD permission flags into initial page-table permissions.

Initial RAM identity pages are broadly supervisor read/write and executable because NXE is not enabled and the PDEs are writable.

Therefore ELF `p_flags` do not establish W^X or read-only code protection at boot.

A guest may create stricter page tables after entry.

## Relocation policy

Protocol v1 does not perform dynamic linking or general ELF relocation.

The guest must already be linked for the addresses represented by its PT_LOAD `p_vaddr` values.

There is no symbol resolver, PLT/GOT loader or relocation engine in the boot path.

## Higher-half ChrisOS incompatibility

The production ChrisOS kernel is a higher-half kernel.

Protocol v1 explicitly rejects higher-half PT_LOAD addresses.

Therefore the real ChrisOS kernel image cannot be booted through v1 merely by pointing ChrisVM at the existing kernel ELF.

This is an explicit protocol limitation, not an accidental test gap.

A future protocol capable of replacing the QEMU/Limine path must define higher-half loading and the boot-information contract required by `kstart`.

## Why v1 must not special-case kstart

A tempting shortcut would be to detect the ChrisOS kernel and jump directly to `kstart` with ad hoc host-created state.

That would hide missing platform contracts.

Protocol v1 instead remains honest: it supports the direct-boot guest ABI it actually implements.

Full ChrisOS boot should arrive through an explicit next protocol/machine version.

## Versioning rule

Any incompatible change to the following requires a boot-protocol version change or a documented compatibility layer:

- reserved physical addresses;
- initial page-table layout;
- segment selectors;
- stack contract;
- framebuffer address/geometry;
- shutdown port;
- ELF address policy;
- register state;
- firmware/boot-information handoff.

Silent mutation would make old guest binaries ambiguous.

## Candidate protocol v2 work

A future protocol intended to boot the real ChrisOS kernel would likely need explicit decisions for:

- higher-half PT_LOAD placement;
- HHDM mapping;
- framebuffer boot information;
- memory-map handoff;
- SMP information;
- ACPI/firmware information;
- kernel virtual/physical ownership;
- real ChrisOS linker-script assumptions;
- device topology;
- transition from host-created boot state into `kstart`.

Those items are roadmap, not v1 behavior.

## Conformance checklist

A protocol-v1 guest can rely on:

- ELF64 little-endian x86-64 direct loading;
- PT_LOAD copied to lower-half `p_vaddr`;
- BSS zeroing;
- identity-mapped RAM;
- long mode already active;
- CPL0;
- initial stack at `0x80000`;
- COM1 at `0x3f8`;
- shutdown port at `0x501`;
- framebuffer at `0x02000000`;
- no firmware services;
- no IDT installed;
- no SMP;
- no disk boot.

Anything outside this list must be established from the revisioned machine specification rather than assumed from a physical PC.

## Revision note

This boot specification was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Protocol v1 is intentionally small and testable. Its most important compatibility boundary is that it boots lower-half direct ELF guests, not the production higher-half ChrisOS kernel.
