---
id: elf-linking
lang: en
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/linker.ld
  - makefile
  - kernel/metal/elf.c
  - kernel/metal/elf.h
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisasm/chrisasm.c
  - tools/test_chrisld.c
  - docs/CHRISLD_STATUS.md
  - docs/CURRENT_SELFHOST_AUDIT.md
  - docs/NATIVE_TOOLCHAIN_AUDIT.md
symbols:
  - kstart
  - __kernel_start
  - __kernel_end
  - __stack_bottom
  - __stack_top
  - elf_load
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
depends_on:
  - boot-information
  - machine-code
  - x86-64-memory-privilege
related:
  - linker-script
  - higher-half-kernel
  - power-on-kstart
  - native-toolchain
  - chrisld
  - chriso
  - kcc
---

# ELF64, object linking and the ChrisOS kernel image

## Scope

The ChrisOS kernel is not a raw sequence of x86-64 instructions. It is an ELF64 executable whose structure tells the bootloader what architecture the image targets, where execution begins, which bytes must be loaded, which virtual addresses those bytes occupy, which memory exists without file payload, and which regions are writable or executable.

The production pipeline is:

~~~text
C / assembly sources
        |
        +-- host GCC
        +-- assembler
        |
        v
relocatable objects
        |
        v
host ld
  -static
  -nostdlib
  -T kernel/metal/linker.ld
        |
        v
kernel.elf
  ELF64
  ET_EXEC
  EM_X86_64
  higher-half
  ENTRY(kstart)
  Limine request segment
        |
        v
Limine
        |
        v
mapped kernel image
~~~

![ELF linking pipeline](../../assets/diagrams/elf-linking-en.svg)

The native ChrisLd is progressing toward this target, but it does not yet generate a production-equivalent kernel image.

## Link-time view and load-time view

ELF has two related views.

At link time, the important entities are sections, symbols and relocations.

At load time, the important entities are program segments and the entry point.

The key distinction is:

~~~text
sections
    primarily serve linkers, debuggers and analysis tools

program headers
    primarily serve loaders
~~~

A bootloader does not need to reconstruct every source section. It needs to construct the runtime memory image described by the program headers.

## ELF object types

Important object types are:

| Type | Meaning |
|---|---|
| ET_REL | relocatable object |
| ET_EXEC | executable |
| ET_DYN | shared object or position-independent executable |
| ET_CORE | core dump |

The final ChrisOS kernel is ET_EXEC. Intermediate compiler objects are relocatable because many final addresses remain unknown until link time.

## Why relocatable objects exist

If one translation unit calls a function defined in another unit, the compiler can emit the calling instruction but cannot yet know the final address of the destination.

The object records:

- machine-code bytes;
- a symbol reference;
- a relocation site;
- a relocation type;
- an addend where applicable.

The linker later assigns addresses, resolves the symbol and patches the instruction or data.

## ELF identification

Every ELF begins with:

~~~text
0x7f 'E' 'L' 'F'
~~~

For the current architecture:

~~~text
EI_CLASS = ELFCLASS64
EI_DATA  = ELFDATA2LSB
~~~

The file therefore uses 64-bit ELF structures and little-endian integer encoding.

## ELF64 header

The executable header is 64 bytes. Important fields are:

| Field | Purpose |
|---|---|
| e_ident | format identity |
| e_type | object type |
| e_machine | target ISA |
| e_version | ELF version |
| e_entry | entry virtual address |
| e_phoff | program-header table offset |
| e_shoff | section-header table offset |
| e_flags | architecture flags |
| e_ehsize | ELF header size |
| e_phentsize | program-header entry size |
| e_phnum | program-header count |
| e_shentsize | section-header entry size |
| e_shnum | section count |
| e_shstrndx | section-name table index |

For x86-64 ELF:

~~~text
e_ehsize    = 64
e_phentsize = 56
e_machine   = 62
~~~

where 62 is EM_X86_64.

## Entry point

The e_entry field contains the virtual address where execution begins.

The production linker script says:

~~~text
ENTRY(kstart)
~~~

The host linker resolves kstart and writes its final virtual address into e_entry. Limine enters there because ChrisOS does not override the executable entry through a Limine Entry Point request.

## Program headers

An ELF64 program header contains:

- p_type;
- p_flags;
- p_offset;
- p_vaddr;
- p_paddr;
- p_filesz;
- p_memsz;
- p_align.

For loading ChrisOS, PT_LOAD is the central segment type.

## PT_LOAD

A PT_LOAD entry means:

~~~text
copy p_filesz bytes
from file offset p_offset

to virtual address p_vaddr

reserve a total of p_memsz bytes
~~~

When p_memsz is greater than p_filesz, the remaining memory bytes are zero-filled.

## File image versus memory image

For one segment:

~~~text
file-backed:
[p_offset, p_offset + p_filesz)

runtime memory:
[p_vaddr, p_vaddr + p_memsz)
~~~

The loader copies the file-backed prefix and zeros the remainder.

This allows the runtime image to be substantially larger than the executable file.

## BSS

Uninitialized or zero-initialized static storage normally occupies BSS.

The production linker script contains:

~~~text
.bss (NOLOAD) : ALIGN(4K) {
    *(.bss .bss.*)
    *(COMMON)
    . = ALIGN(16);
    __stack_bottom = .;
    . += 1024K;
    __stack_top = .;
    . = ALIGN(4K);
    __kernel_end = .;
} :data
~~~

This collects BSS, includes common symbols, reserves one MiB for the linker-managed kernel stack region and defines kernel boundary symbols without storing one MiB of zero bytes in the file.

## p_filesz and p_memsz

If a writable segment had 12 KiB of initialized data, 40 KiB of BSS and a 1024 KiB reserved stack, conceptually:

~~~text
p_filesz = initialized data
p_memsz  = initialized data + BSS + stack
~~~

Alignment can add gaps.

The difference becomes zero-filled runtime storage.

## Segment permissions

ELF program-header flags are:

~~~text
PF_X = 1
PF_W = 2
PF_R = 4
~~~

The production script defines:

~~~text
requests PT_LOAD FLAGS(6)  -> R | W
text     PT_LOAD FLAGS(5)  -> R | X
data     PT_LOAD FLAGS(6)  -> R | W
~~~

No declared production PT_LOAD is both writable and executable.


## Limine request segment

The request segment contains the three linker input classes used by the Limine protocol:

~~~text
.limine_requests_start
.limine_requests
.limine_requests_end
~~~

It is writable because the bootloader writes response pointers into request objects before kernel entry. It is not executable.

This is a direct example of ELF segment permissions expressing a protocol contract rather than merely a compiler convention.

## Text and rodata

The linker assigns both .text and .rodata to the text program header.

Consequently, constants in .rodata are currently mapped by the same RX segment as executable code. They are not writable, but the page-level executable permission is shared with text.

A stricter future policy could split:

~~~text
RX text
R  rodata
RW data
~~~

in addition to the Limine request segment.

The current layout still avoids writable executable pages.

## Data

The .data and .bss output sections belong to the RW data segment.

The linker-reserved stack also expands this segment's runtime memory size.

Initialized variables consume file bytes. BSS and reserved stack space mainly consume p_memsz.

## Alignment

The host link uses:

~~~text
-z max-page-size=0x1000
~~~

and major output sections are aligned to 4 KiB.

The load-segment alignment rule requires:

~~~text
p_vaddr mod p_align
=
p_offset mod p_align
~~~

A linker therefore cannot independently choose arbitrary file offsets and virtual addresses.

## p_paddr

The ELF64 program header includes both p_vaddr and p_paddr.

For the ChrisOS boot path, Limine chooses actual physical backing while honoring the executable virtual layout.

The higher-half p_vaddr is not evidence that the executable physically occupies a high canonical address. Kernel memory accounting must not derive physical placement from the link address.

## Sections

Typical ELF sections include:

~~~text
.text
.rodata
.data
.bss
.symtab
.strtab
.rela.text
.rela.data
~~~

Sections describe logical units of code, data and metadata.

The section header contains fields such as:

- sh_name;
- sh_type;
- sh_flags;
- sh_addr;
- sh_offset;
- sh_size;
- sh_link;
- sh_info;
- sh_addralign;
- sh_entsize.

Important flags describe allocatable, writable and executable content.

## Section versus segment

One load segment can contain several sections.

ChrisOS demonstrates:

~~~text
PT_LOAD text
  .text
  .rodata
~~~

and:

~~~text
PT_LOAD data
  .data
  .bss
  linker-reserved stack
~~~

The linker groups sections into runtime segments. The loader maps segments.

## Why section headers are not the primary boot map

Limine loads the kernel according to the executable program headers.

A final executable can remain bootable without many nonessential section-header details if the entry point and program headers remain correct.

Section headers still matter for:

- debugging;
- disassembly;
- symbolization;
- object inspection;
- linker input processing.

## Symbols

A symbol represents a named program entity.

Relevant attributes include:

- name;
- value or section-relative offset;
- size;
- binding;
- type;
- defining section.

Common bindings include local, global and weak.

Common symbol kinds include function, object, section and no-type.

## Local symbols

Local symbols are internal to one object or link unit.

They can represent private functions, local labels or internal data without entering global resolution.

## Global symbols

Global symbols can satisfy references from other objects.

Two incompatible strong global definitions with the same name normally cause a link failure.

The current ChrisLd rejects duplicate global definitions.

## Undefined symbols

An undefined symbol means an object uses a name but does not define it.

A final static linker must resolve the dependency.

If no valid definition exists, the link must fail.

A static kernel cannot safely retain an unpatched branch or pointer.

## Symbol addresses after layout

Before final layout, a symbol can be represented as a section-relative offset.

After layout:

~~~text
S =
output section base
+ input object placement
+ symbol offset
~~~

The current ChrisLd computes this relation independently for text, rodata, data and BSS.

## Relocations

A relocation instructs the linker how to transform a symbol reference into final bytes.

Standard notation uses:

~~~text
S = resolved symbol address
A = addend
P = address of relocation place
~~~

Representative formulas are:

~~~text
R_X86_64_64:
S + A

R_X86_64_PC32:
S + A - P

R_X86_64_PLT32:
S + A - P
~~~

for the direct static binding used by the current ChrisLd.

## REL and RELA

REL encodes the addend implicitly in the relocation target bytes.

RELA stores the addend explicitly in the relocation record.

x86-64 ELF commonly uses RELA semantics.

ChrisO v2 stores a signed addend explicitly in each ChrisoRel record.

## R_X86_64_64

This relocation writes a complete 64-bit absolute value.

It is useful for final absolute pointers whose addresses were unknown during object generation.

The relocation site must provide eight writable output bytes.

## R_X86_64_PC32

PC32 writes a signed 32-bit value derived from:

~~~text
S + A - P
~~~

The result must fit:

~~~text
-2147483648 .. 2147483647
~~~

Current ChrisLd explicitly rejects values outside that range.

## R_X86_64_PLT32

Compilers commonly emit PLT32 relocations for external function calls.

In a final static link, a linker can often bind the destination directly rather than preserve a runtime Procedure Linkage Table entry.

Current ChrisLd applies the same signed PC-relative displacement formula used for PC32.

## R_X86_64_32

This represents a 32-bit absolute relocation with zero-extension constraints in the complete ABI.

Current ChrisLd rejects values above 0xffffffff.

## R_X86_64_32S current limitation

R_X86_64_32S has signed-32 extension semantics in the x86-64 ABI.

Current ChrisLd sends R_X86_64_32S through the same upper-bound check used by R_X86_64_32.

It therefore does not yet model the complete signed-32 validity rule.

This is a current-source limitation, not a theoretical limitation of ELF.

## Why relocation overflow must fail

Truncating an out-of-range PC-relative displacement produces machine code that branches to the wrong address.

A linker must reject an unrepresentable relocation or choose another code sequence.

Correct linking is a semantic transformation, not simple concatenation.

## Kernel code model

The production compiler uses:

~~~text
-mcmodel=kernel
~~~

This selects x86-64 addressing assumptions appropriate to a kernel placed in the high canonical region.

The compiler's code model and the linker's virtual layout must agree.

## Fixed-address non-PIE image

The build also uses:

~~~text
-fno-pic
-fno-pie
~~~

and linker.ld fixes the base to:

~~~text
0xffffffff80000000
~~~

The current ChrisOS kernel is a fixed-address ET_EXEC image, not a PIE/KASLR kernel.

## Static and freestanding link

The host linker receives:

~~~text
-nostdlib
-static
~~~

The kernel therefore does not automatically import host startup files, libc initialization or a userspace runtime linker.

All ordinary kernel dependencies must be resolved from the explicitly supplied objects.

## Why nostdlib is important

A freestanding kernel cannot depend on assumptions supplied by a hosted process environment, such as:

- libc startup;
- host syscalls;
- userspace TLS initialization;
- process environment setup;
- host dynamic loader behavior.

nostdlib prevents these dependencies from entering accidentally.

## Why static is important

At kernel boot there is no userspace ELF interpreter available to resolve ordinary dynamic imports.

The kernel executable must already contain or directly resolve what it needs for entry and initialization.

## Linker script as policy

ELF supplies the mechanisms, while kernel/metal/linker.ld defines the ChrisOS policy.

It controls:

- output format;
- architecture;
- entry symbol;
- virtual base;
- program headers;
- section order;
- alignment;
- Limine metadata placement;
- stack reservation;
- exported boundary symbols;
- discarded sections.

The next chapter studies this policy in detail.

## Linker-defined symbols

The script creates symbols not defined by a C object:

~~~text
__kernel_start
__kernel_end
__stack_bottom
__stack_top
~~~

Linker-defined symbols turn layout boundaries into names the kernel can reference.

## Kernel start and end

__kernel_start is assigned at the higher-half base before the output sections.

__kernel_end is assigned after BSS, the stack reservation and final page alignment.

These addresses describe the linked virtual extent of the kernel image.

## Stack symbols

The script aligns to 16 bytes, records __stack_bottom, advances the location counter by 1024 KiB, records __stack_top and finally page-aligns the end.

This reserves runtime memory without storing one MiB of zero data in the ELF file.

## COMMON symbols

The BSS collection includes:

~~~text
*(COMMON)
~~~

This supports object forms where tentative C definitions are represented as common symbols.

## Discarded metadata

The production script discards:

~~~text
.eh_frame*
.note*
.comment*
~~~

The current kernel does not depend on host-style unwind metadata, generic note records or compiler comment strings.

If future debugging or unwinding requires these sections, the discard policy must change explicitly.

## Section ordering

The production layout is:

~~~text
0xffffffff80000000
    |
    +-- Limine requests
    +-- text
    +-- rodata
    +-- data
    +-- bss
    +-- one-MiB reserved stack
    |
__kernel_end
~~~

Major sections are page aligned.

Section order affects addresses, relocation values and the final executable hash.
