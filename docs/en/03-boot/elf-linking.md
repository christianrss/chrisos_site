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
