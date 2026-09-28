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


## Object order and reproducibility

The makefile supplies the kernel object files to ld in a deterministic order.

Input sections are concatenated according to linker policy and input ordering. Reordering objects can change:

- function addresses;
- global addresses;
- relocation displacements;
- padding;
- final kernel hash.

A changed binary is not automatically wrong. Deterministic input ordering is still important for reproducible diagnostics.

## GOT and PLT

Position-independent and dynamically linked programs frequently use the Global Offset Table and Procedure Linkage Table.

The current kernel disables PIE/PIC and has no userspace dynamic loader dependency.

A full runtime GOT/PLT resolver is therefore not part of the production boot requirement.

An input object may still contain a PLT32 relocation that the static linker resolves directly.

## Dynamic ELF structures

A dynamically linked executable can contain:

~~~text
PT_DYNAMIC
.dynamic
.dynsym
.dynstr
.rela.dyn
.rela.plt
~~~

The production kernel does not depend on these structures.

Its boot model is intentionally:

~~~text
static ET_EXEC
+
PT_LOAD segments
+
fixed entry
~~~

## Authoritative host link command

The production link is equivalent to:

~~~text
ld
-m elf_x86_64
-nostdlib
-static
-z max-page-size=0x1000
-z noexecstack
-T kernel/metal/linker.ld
-o kernel.elf
<object list...>
~~~

The makefile then invokes stamp_kernel on the result.

At the reviewed revision, this host link remains authoritative.

## Post-link stamping

The final production artifact is not solely raw ld output.

The makefile runs:

~~~text
stamp_kernel kernel.elf
~~~

after linking.

A future self-hosted production pipeline therefore has to reproduce the intended post-link provenance semantics as well as ELF linking.

## Current ChrisO version 2

The current source defines ChrisO version 2.

Its section classes are:

~~~text
TEXT
RODATA
DATA
BSS
~~~

Symbols contain:

- name;
- section;
- offset;
- size;
- binding;
- kind.

Relocations contain:

- target section;
- target offset;
- symbol index;
- signed addend;
- relocation type.

This is materially more capable than some older audit snapshots in the repository describe.

## ChrisO is not ELF ET_REL

ChrisO is a project-specific relocatable format.

The native pipeline is:

~~~text
KCC / ChrisAsm
      |
      v
ChrisO
      |
      v
ChrisLd
      |
      v
ELF64 ET_EXEC
~~~

There is no requirement that the internal object format itself be ELF if it carries all information needed for correct final linking.

## Current ChrisLd multi-object link

The current chrisld_link_objects implementation:

- accepts multiple ChrisO objects;
- packs section classes;
- resolves globals;
- rejects duplicate global definitions;
- resolves undefined symbols;
- applies relocation records;
- emits ELF64;
- performs structural validation.

This is significantly beyond the older one-object text-only linker.

## Current ChrisLd section layout

The current source can emit:

~~~text
PT_LOAD RX
  text
  rodata

PT_LOAD RW
  data
  bss memory
~~~

The second load segment is emitted when data or BSS exists.

## BSS in current ChrisLd

For its writable segment, ChrisLd sets the file-backed size from data and the memory size from data plus BSS.

Conceptually:

~~~text
p_filesz = data
p_memsz  = data + bss
~~~

This correctly represents zero-filled BSS at load time.

## Current symbol resolution

For every relocation, ChrisLd:

1. reads the relocation symbol;
2. distinguishes defined/local/global/undefined state;
3. searches global definitions;
4. rejects ambiguity;
5. computes the final symbol address;
6. computes the relocation place;
7. applies the relocation;
8. rejects invalid type or overflow.

This is the essential static-link algorithm.

## Exact entry matching

Current ChrisLd searches for the exact symbol:

~~~text
kstart
~~~

then exact:

~~~text
main
~~~

and otherwise falls back to the supplied load address.

This is more correct than older snapshot documentation that described prefix matching.

## Current ChrisLd validation

chrisld_validate checks:

- ELF magic;
- ELFCLASS64;
- little endian;
- EM_X86_64;
- program-header entry size;
- nonzero program-header count;
- p_filesz <= p_memsz;
- no writable and executable load segment;
- non-overlapping load segments;
- entry inside an executable load segment.

These checks establish a useful structural baseline.

They do not prove equivalence to the production linker script.

## Current source versus older audit documents

Some repository audit files explicitly describe earlier snapshots.

They can therefore lag the current source.

At da3df29, the source already includes BSS, data, rodata, multiple objects and relocation types that older prose says are absent.

For this documentation corpus:

~~~text
reviewed source at the current revision
is implementation truth

historical audit documents
are progress records
~~~

Both are useful, but they serve different purposes.

## What ChrisLd still lacks for production kernel.elf

The current native linker still does not reproduce all kernel policy.

Major missing requirements include:

- a distinct Limine request PT_LOAD;
- collection of request start, request body and request end sections;
- explicit KEEP-equivalent semantics;
- one-MiB linker-reserved stack;
- __kernel_start;
- __kernel_end;
- __stack_bottom;
- __stack_top;
- exact output-section ordering of linker.ld;
- discard policy;
- full production-scale object count;
- all relocation/code-generation combinations required by the complete kernel;
- proof that the image is accepted by Limine;
- proof that it reaches ChrisOS boot markers.

Therefore:

~~~text
ChrisLd emits ELF64
does not imply
ChrisLd links production kernel.elf
~~~

## Object-count limit

Current ChrisLd defines:

~~~text
LD_OBJS = 32
~~~

The production makefile contains substantially more than 32 kernel objects.

This is an immediate scalability mismatch.

## Output-size limit

The current native linker defines:

~~~text
CHRISLD_ELF_MAX = 1 MiB
~~~

A production linker cannot assume the full kernel will remain below a small fixed bootstrap ceiling.

The output mechanism eventually needs to scale with actual image size.

## ChrisO fixed capacities

Current ChrisO includes fixed limits such as:

~~~text
CHRISO_SYM_MAX = 256
CHRISO_REL_MAX = 512
~~~

These limits are useful during bootstrap.

They must be measured against the complete kernel before production claims are made.

## Internal alignment differences

ChrisLd packs object section contributions with 16-byte internal alignment and creates page-aligned segment structure.

The host kernel script page-aligns each major output section.

These layouts are not equivalent.

Different layouts can both produce correct programs, but linker-generated boundary symbols, Limine metadata placement and boot permissions must still match the required semantics.

## Current p_paddr simplification

The current ChrisLd helper writes the same address to p_vaddr and p_paddr.

For the higher-half Limine kernel, physical placement is loader-controlled.

The native linker must therefore treat p_paddr as an ELF field whose policy must be validated, not as a claim that high canonical virtual addresses are physical RAM locations.

## User ELF loader inside ChrisOS

kernel/metal/elf.c loads user executables, not kernel.elf.

It provides an independent implementation of loader-side ELF validation.

It checks:

- ELF64;
- little endian;
- ET_EXEC;
- EM_X86_64;
- program-header bounds;
- a program-header count limit;
- only PT_NULL and PT_LOAD;
- p_filesz <= p_memsz;
- no W+X segment;
- page congruence between offset and virtual address;
- user virtual-address window;
- non-overlapping load segments;
- entry inside an executable segment.

## User virtual-address policy

The current user loader restricts executable mapping to:

~~~text
USER_LOAD_LO = 0x400000
USER_LOAD_HI = 0x500000
~~~

This is unrelated to the higher-half kernel range.

ELF is a format; each loader applies its own address-space policy.

## User BSS behavior

The user loader allocates zeroed physical pages before copying file-backed bytes.

The unfilled portion therefore remains zero.

This naturally implements p_memsz greater than p_filesz semantics.

## User W^X

The loader translates write permission to MM_WRITE and absence of execute permission to MM_NX.

It rejects a segment that is simultaneously writable and executable.

This matches ChrisLd validation and the production linker's W^X policy.

## Entry validation

The user loader verifies that the entry falls inside an executable PT_LOAD.

ChrisLd validates the same property for its emitted files.

This prevents transfer of control to a data-only segment.

## Segment overlap

The user loader rejects overlapping PT_LOAD virtual ranges.

ChrisLd also rejects overlap during validation.

Overlaps can create ambiguous permissions, file-copy order and zero-fill behavior.

Rejecting them keeps the memory model simple.

## File-range arithmetic

The user loader uses checked arithmetic rather than trusting:

~~~text
offset + size
~~~

blindly.

The safe pattern is:

~~~text
size <= limit
and
offset <= limit - size
~~~

This avoids unsigned wraparound.

Executable parsing is a security boundary even in a small operating system.

## Static-link algorithm

A minimal production-quality static linker follows a sequence like this.

### Parse objects

Read section payloads, symbol records, relocation records and metadata.

### Validate objects

Reject invalid offsets, counts and malformed records.

### Group sections

Assign input material to output classes such as:

~~~text
requests
text
rodata
data
bss
~~~

### Assign addresses

Choose aligned virtual addresses for the output classes.

### Place each input object

Record where every input section lands inside its output class.

### Build global symbol table

Collect global definitions and reject duplicates.

### Resolve undefined symbols

Every required external dependency must bind to a valid definition.

### Compute final symbol addresses

For each symbol:

~~~text
S =
output class base
+ object placement
+ symbol offset
~~~

### Apply relocations

Patch code and data with the relocation-specific formula.

### Emit file-backed data

Write text, rodata and data.

### Represent zero-fill storage

Use p_memsz beyond p_filesz for BSS and linker-reserved zero storage.

### Emit ELF metadata

Write the ELF header and program-header table.

### Validate final image

Check entry, permissions, overlap, alignment and size relationships.

Current ChrisLd implements a bootstrap subset of this pipeline.

## Linking is a dependency graph

Object files form a graph.

Example:

~~~text
start.o
  -> serial_init
  -> bootinfo_init
  -> gdt_init

serial.o
  -> outb
  -> inb
~~~

Definitions form nodes and symbol references form edges.

A final static link must resolve all required edges.

## Layout must precede final relocation

A symbol's final address depends on:

- output section base;
- object ordering;
- alignment;
- previous input sizes;
- linker-reserved regions;
- segment layout.

Relocation therefore generally requires layout to be known first.

Naive one-pass concatenation does not scale to a real kernel.

## Link-time garbage collection

General linkers may remove unused sections.

Limine requests are externally discovered data; normal code reachability may not reference them.

That is why the production script uses KEEP.

A future native linker with dead-section elimination needs an equivalent concept of externally rooted sections.

## Deterministic linking

For the same explicit inputs, link layout should be deterministic.

Sources of unwanted nondeterminism include:

- unstable object order;
- hash-table iteration order;
- uninitialized padding;
- implicit timestamps;
- random IDs.

ChrisOS intentionally embeds build provenance, so different build IDs can still create different bytes even when layout is deterministic.

## Link map files

A production ChrisLd should eventually emit a linker map containing:

- output sections;
- addresses;
- sizes;
- object placement;
- symbol addresses;
- segment permissions.

This is valuable for crash symbolization, size regression and comparison against host ld.

## Differential linker gate

A strong self-hosting test can link a compatible object set with both host ld and ChrisLd.

Compare semantic output such as:

- entry;
- higher-half placement;
- segment permissions;
- p_filesz and p_memsz;
- required symbols;
- relocation targets;
- Limine request discoverability.

Byte-for-byte equality is not required if both images obey the same runtime contract.

## Production-equivalence gate

A meaningful ChrisLd kernel milestone should require at least:

~~~text
ELFCLASS64
ET_EXEC
EM_X86_64
ENTRY(kstart)
higher-half layout
Limine request RW segment
RX code
RW data
BSS zero-fill
one-MiB stack reservation
kernel boundary symbols
all required symbols resolved
no W+X PT_LOAD
Limine accepts image
QEMU reaches ChrisOS markers
~~~

Only then is the statement "ChrisLd links the kernel" technically justified.

## Current self-hosting boundary

The repository does not currently prove SH4 or SH5.

The native compiler still does not compile the entire kernel.

Native assembly still has blockers.

ChrisLd has not produced a production BIN/KERNEL.ELF that has booted.

The production image remains host-built and host-linked.

## Reproducible checker

scripts/check_elf_linking_examples.py validates:

1. ELF64 header sizes and EM_X86_64.
2. program-header flag arithmetic.
3. zero-fill semantics from p_filesz and p_memsz.
4. PT_LOAD alignment congruence.
5. R_X86_64_64, PC32 and PLT32 formulas.
6. signed PC32 overflow rejection.
7. production ENTRY(kstart).
8. higher-half base.
9. three production load-segment policy classes.
10. BSS NOLOAD and the one-MiB stack reservation.
11. host linker flags.
12. current ChrisO v2 section, symbol and relocation model.
13. current ChrisLd multi-object and relocation support.
14. current production-kernel gaps.
15. user ELF loader W^X, overlap and bounds contracts.

The checker does not invoke host ld and does not build kernel.elf.

## Current implementation matrix

| Capability | Host production link | Current ChrisLd |
|---|---:|---:|
| ELF64 ET_EXEC | yes | yes |
| EM_X86_64 | yes | yes |
| higher-half virtual address | yes | can emit |
| exact kstart entry | yes | yes |
| multiple input objects | yes | yes, limited |
| global symbol resolution | yes | yes |
| duplicate global rejection | yes | yes |
| undefined symbol rejection | yes | yes |
| R_X86_64_64 | yes | yes |
| R_X86_64_PC32 | yes | yes |
| R_X86_64_PLT32 | yes | yes |
| R_X86_64_32 | yes | yes |
| R_X86_64_32S full semantics | yes | partial |
| text | yes | yes |
| rodata | yes | yes |
| data | yes | yes |
| BSS zero-fill | yes | yes |
| separate RX and RW loads | yes | yes |
| dedicated Limine request load | yes | no |
| linker-script policy | yes | no |
| one-MiB kernel stack reservation | yes | no |
| kernel boundary symbols | yes | no |
| Limine KEEP semantics | yes | no |
| full production object count | yes | no |
| production kernel boot | yes | not proven |

## Validation boundary

This chapter is reconciled to:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

The authoritative production path remains:

~~~text
host GCC / assembler
+
host ld
+
kernel/metal/linker.ld
~~~

Current source is treated as implementation truth when historical audit documents describe older snapshots.

Run:

~~~text
python scripts/check_elf_linking_examples.py --source .source
~~~

## Review triggers

Review this chapter when:

- production linker flags change;
- kernel virtual base changes;
- program-header policy changes;
- rodata receives a separate read-only segment;
- new relocation types appear;
- ChrisO format changes;
- ChrisLd capacity limits change;
- ChrisLd implements Limine request handling;
- ChrisLd implements kernel linker policy;
- stack reservation moves;
- native tools link BIN/KERNEL.ELF;
- a ChrisLd-built kernel boots successfully.

## Primary references

- System V ABI, Generic ELF specification.
- AMD64 System V ABI relocation definitions.
- ChrisOS linker script and makefile.
- Current ChrisO, ChrisLd and user ELF-loader sources listed in front matter.
