---
id: linker-script
lang: en
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/linker.ld
  - kernel/metal/start.c
  - kernel/metal/pmm.c
  - kernel/metal/mm.c
  - kernel/metal/bootinfo.c
  - makefile
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chriso.h
  - docs/CHRISLD_STATUS.md
  - docs/CURRENT_SELFHOST_AUDIT.md
symbols:
  - kstart
  - __kernel_start
  - __kernel_end
  - __stack_bottom
  - __stack_top
depends_on:
  - elf-linking
related:
  - higher-half-kernel
  - power-on-kstart
  - limine
  - boot-information
  - physical-memory
  - virtual-memory
  - chrisld
---

# GNU ld linker scripts and the ChrisOS kernel layout

## Scope

A linker script is an executable description of how independently compiled object files become one address space.

The compiler and assembler can produce code and data fragments, symbols and relocations. They do not decide the complete kernel memory map. The linker must decide where the kernel begins, where every category of input section is placed, how the resulting ELF program headers are formed, which metadata must survive section elimination, where zero-filled state exists, and which addresses should become named symbols visible to the kernel.

The current ChrisOS production script is compact:

~~~text
OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(kstart)

PHDRS {
    requests PT_LOAD FLAGS(6);
    text     PT_LOAD FLAGS(5);
    data     PT_LOAD FLAGS(6);
}

SECTIONS {
    . = 0xffffffff80000000;
    __kernel_start = .;

    .limine_requests : ALIGN(4K) {
        KEEP(*(.limine_requests_start))
        KEEP(*(.limine_requests))
        KEEP(*(.limine_requests_end))
    } :requests

    .text : ALIGN(4K) {
        *(.text .text.*)
    } :text

    .rodata : ALIGN(4K) {
        *(.rodata .rodata.*)
    } :text

    .data : ALIGN(4K) {
        *(.data .data.*)
    } :data

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

    /DISCARD/ : {
        *(.eh_frame*)
        *(.note*)
        *(.comment*)
    }
}
~~~

The file is short, but it defines the production kernel virtual layout, segment protection model, Limine request placement, BSS semantics, stack reservation and exported boundary symbols.

![ChrisOS linker-script evaluation](../../assets/diagrams/linker-script-en.svg)

## Every link uses a linker script

GNU ld always operates under a linker script. If the build does not supply one explicitly, ld uses a built-in default script.

ChrisOS does not use the default.

The makefile passes:

~~~text
-T kernel/metal/linker.ld
~~~

which makes the project-owned script the main layout policy.

This is important for an operating-system kernel because the generic host layout would not know about:

- the higher-half virtual base;
- Limine request sections;
- the kernel stack reservation;
- ChrisOS linker symbols;
- the desired program-header protection classes.

## The script is a language

GNU linker scripts contain commands, assignments and expressions.

ChrisOS uses several categories:

- file/output commands: OUTPUT_FORMAT, OUTPUT_ARCH, ENTRY;
- program-header declaration: PHDRS;
- output layout: SECTIONS;
- wildcard input-section selection;
- expressions involving the location counter;
- symbol assignments;
- output-section attributes such as ALIGN and NOLOAD;
- retention policy through KEEP;
- explicit removal through /DISCARD/.

The script should therefore be understood as a small program whose result is an ELF layout.

## Input sections

Compiler and assembler outputs contain input sections.

Representative names include:

~~~text
.text
.text.start
.text.some_function
.rodata
.rodata.str1.1
.data
.data.some_global
.bss
.bss.some_buffer
~~~

Each input object contributes zero or more sections.

The linker combines these sections according to output-section rules.

## Output sections

An output section is created by the linker script.

For example:

~~~text
.text : ALIGN(4K) {
    *(.text .text.*)
} :text
~~~

creates an output section named .text and fills it using matching input sections.

An output section has:

- a location in the output address space;
- a size;
- alignment;
- selected input contents;
- optional attributes;
- zero or more program-header assignments.

## Input-section wildcard syntax

The expression:

~~~text
*(.text .text.*)
~~~

means:

~~~text
from every input file:
    collect input section .text
    and every input section matching .text.*
~~~

The first star selects any input file.

The names inside parentheses select sections.

This mechanism allows one rule to catch compiler-generated subsection names.

## Why subsection wildcards matter

A compiler can split code into more specific sections.

Examples include:

~~~text
.text.kstart
.text.serial_init
.text.bootinfo_init
~~~

A script that matched only .text could miss them.

The pattern .text.* makes the collection robust to that style of object generation.

The same strategy is used for rodata, data and BSS.

## Input ordering

The linker script controls the order of broad output categories.

The makefile and linker control the order of input contributions within those categories.

Changing object order can change:

- function addresses;
- data addresses;
- relocation displacements;
- padding;
- final kernel hash.

The script and the object list jointly determine the final layout.

## OUTPUT_FORMAT

ChrisOS begins with:

~~~text
OUTPUT_FORMAT(elf64-x86-64)
~~~

This selects the GNU BFD output format.

The intended final container is a 64-bit x86 ELF executable.

OUTPUT_FORMAT does not cause C code to become x86-64. Machine-code generation is the compiler/assembler responsibility.

The linker must receive compatible objects.

## OUTPUT_ARCH

The script declares:

~~~text
OUTPUT_ARCH(i386:x86-64)
~~~

This selects x86-64 as the output architecture in GNU ld/BFD naming.

The i386 prefix belongs to the BFD architecture naming scheme. It does not mean ChrisOS is linked as a 32-bit executable.

## ENTRY

ChrisOS declares:

~~~text
ENTRY(kstart)
~~~

ENTRY tells the linker which symbol should define the executable entry point.

The chain is:

~~~text
symbol kstart
    |
symbol resolution
    |
final virtual address
    |
ELF e_entry
    |
Limine handoff
~~~

The Limine chapter documents why the bootloader eventually transfers control to this address.

## ENTRY is a link-time name

ENTRY does not call a function.

It does not generate a jump.

It selects a symbol whose final address becomes ELF metadata.

The bootloader is the component that later uses that metadata to establish the initial instruction pointer.

## Entry-point validation

A correct executable should have its entry inside an executable load segment.

The script causes normal code to be collected into .text and assigns .text to the RX program header named text.

Therefore kstart is expected to reside in executable memory.

This should still be verified against the final ELF.

## PHDRS

ChrisOS explicitly defines:

~~~text
PHDRS {
    requests PT_LOAD FLAGS(6);
    text     PT_LOAD FLAGS(5);
    data     PT_LOAD FLAGS(6);
}
~~~

PHDRS defines the ELF program-header policy instead of allowing GNU ld to infer the complete segment model automatically.

The names requests, text and data exist in the linker-script namespace and are referenced later from SECTIONS.

## PHDR names

The names:

~~~text
requests
text
data
~~~

do not become ordinary program symbols.

They are labels used by the script to connect output sections to program headers.

For example:

~~~text
:text
~~~

means:

~~~text
place this output section in the program header named text
~~~

## PHDRS and ELF output

GNU ld uses PHDRS meaningfully for ELF-style program headers.

Once PHDRS is specified, the script is taking explicit control over the output segment table.

That is appropriate for a bootable kernel where segment permissions are part of the architecture.

## PT_LOAD

Every ChrisOS program header declared here is PT_LOAD.

PT_LOAD means the segment contributes to the runtime image that the loader constructs.

Current conceptual roles are:

~~~text
requests
    boot protocol metadata

text
    executable code and constants

data
    mutable data, BSS and stack reservation
~~~

## Program-header flags

ELF uses:

~~~text
PF_X = 1
PF_W = 2
PF_R = 4
~~~

Therefore:

~~~text
FLAGS(5) = PF_R | PF_X
FLAGS(6) = PF_R | PF_W
~~~

The current policy is:

| PHDR | Flags | Role |
|---|---|---|
| requests | RW | Limine requests |
| text | RX | code + rodata |
| data | RW | data + BSS + stack |

No production PT_LOAD is writable and executable simultaneously.

## W^X as a linker property

Writable-versus-executable separation is not only a page-table concern.

The ELF segment flags originate in the link.

The bootloader uses those flags to construct the initial executable image mappings.

Therefore linker policy participates in W^X.

A change to PHDR flags can change kernel protection semantics without changing C source.

## SECTIONS

The SECTIONS block describes the output address-space layout.

ChrisOS begins:

~~~text
SECTIONS {
    . = 0xffffffff80000000;
    __kernel_start = .;
~~~

The special symbol dot is the location counter.

The script starts layout at the higher-half kernel virtual base and immediately records that value in a linker-defined symbol.

## The location counter

Dot represents the current output location.

ChrisOS uses it in four important ways.

Set an absolute starting location:

~~~text
. = 0xffffffff80000000;
~~~

Capture a boundary:

~~~text
__kernel_start = .;
~~~

Align a boundary:

~~~text
. = ALIGN(16);
~~~

Reserve address space:

~~~text
. += 1024K;
~~~

The location counter is therefore state, not a decorative syntax element.

## Assigning dot changes layout

An assignment to dot changes where later output resides.

This operation:

~~~text
. += 1024K;
~~~

does not merely calculate a number.

It moves the output location forward by one MiB.

Any symbol defined after it receives a correspondingly higher value.

Any subsequent section begins later.

## Higher-half base

The initial value is:

~~~text
0xffffffff80000000
~~~

This is the virtual address at which ChrisOS is linked.

It is not the physical location chosen by Limine.

The higher-half kernel chapter explains how link-time virtual addresses and bootloader-created mappings cooperate.

## __kernel_start

The script immediately executes:

~~~text
__kernel_start = .;
~~~

At the current layout this symbol has the value:

~~~text
0xffffffff80000000
~~~

The assignment does not allocate bytes.

It creates a named address equal to the current location counter.

## Linker symbols as addresses

A linker-defined boundary symbol is generally interpreted by taking its address.

Conceptually:

~~~text
extern char __kernel_start[];
kernel_start = address of __kernel_start
~~~

It is not an ordinary variable whose memory must contain the numeric address.

This distinction matters when C code consumes linker-defined symbols.

## Output-section alignment

The first section is:

~~~text
.limine_requests : ALIGN(4K) {
    ...
}
~~~

and each major section uses 4-KiB alignment.

Alignment rounds the beginning of the section to an address compatible with the requested boundary.

## ALIGN arithmetic

For a power-of-two alignment A:

~~~text
align_up(x, A)
=
(x + A - 1) & ~(A - 1)
~~~

Examples for 4096:

~~~text
0x1000 -> 0x1000
0x1001 -> 0x2000
0x1fff -> 0x2000
0x2000 -> 0x2000
~~~

The chapter checker validates representative calculations.

## ALIGN as expression versus section placement

GNU ld ALIGN is an expression helper.

When used as the address expression of an output section, the aligned result determines the output-section start.

When assigned back to dot:

~~~text
. = ALIGN(16);
~~~

the location counter itself moves.

Understanding the context is important because ALIGN by itself computes a value; the surrounding section syntax or assignment determines whether layout changes.

## Why page-align major sections

ChrisOS page-aligns:

- Limine requests;
- text;
- rodata;
- data;
- BSS.

Benefits include:

- page-level protection boundaries;
- predictable segment layout;
- easier memory accounting;
- easier ELF inspection;
- simpler future remapping.

Alignment may also create unused gaps.

## Limine request output section

The first output section is:

~~~text
.limine_requests : ALIGN(4K) {
    KEEP(*(.limine_requests_start))
    KEEP(*(.limine_requests))
    KEEP(*(.limine_requests_end))
} :requests
~~~

It is a protocol section rather than ordinary application data.

Limine discovers objects in this region.

The kernel source places those objects into special input sections using compiler attributes.

## The request pipeline

The full path is:

~~~text
bootinfo.c section attribute
        |
input object special section
        |
linker wildcard selection
        |
KEEP
        |
.limine_requests output section
        |
:requests program header
        |
Limine scanning
~~~

Every stage is necessary.

Dropping section identity anywhere in the toolchain breaks the boot ABI.

## KEEP

KEEP protects matched input sections from linker garbage collection.

This matters because Limine request objects can be externally consumed without ordinary code references.

A pure symbol-reachability graph may consider such data unused.

KEEP says that these sections must survive even when section garbage collection is enabled.

## External reachability

Limine is outside the kernel executable's normal relocation graph.

This creates a general pattern:

~~~text
section used by external scanner
        |
normal code may not reference it
        |
garbage collector cannot infer importance
        |
explicit retention is required
~~~

Other systems use similar techniques for initcall tables, firmware descriptors, interrupt tables and registries.

## Request ordering

The linker script places:

~~~text
.limine_requests_start
then
.limine_requests
then
.limine_requests_end
~~~

The ordering defines the delimited request region expected by the protocol version used by ChrisOS.

A future native linker must preserve semantic ordering, not merely preserve all bytes.

## Program-header assignment of requests

The suffix:

~~~text
:requests
~~~

assigns the output section to the PHDR named requests.

That PHDR is RW.

The section name and the PHDR name are separate namespaces and serve different purposes.

## Text section

The text rule is:

~~~text
.text : ALIGN(4K) {
    *(.text .text.*)
} :text
~~~

It gathers executable code into a page-aligned output section and assigns it to the RX program header.

## Per-function sections

If the compiler emits:

~~~text
.text.kstart
.text.foo
.text.bar
~~~

the .text.* pattern includes them.

This makes the script resilient to compiler subsection naming without listing every function.

## Rodata section

The rodata rule is:

~~~text
.rodata : ALIGN(4K) {
    *(.rodata .rodata.*)
} :text
~~~

It creates a distinct output section but assigns it to the same RX PHDR as .text.

Therefore:

~~~text
output section boundary
is not necessarily
program segment boundary
~~~

This distinction is central to ELF linking.

## Current rodata tradeoff

Because rodata shares the RX segment, constants are executable at page-permission level.

They are not writable.

A stricter layout could create an R-only program header for rodata.

Current source does not do this.

## Data section

The rule:

~~~text
.data : ALIGN(4K) {
    *(.data .data.*)
} :data
~~~

collects initialized mutable storage and assigns it to the RW data PHDR.

These bytes normally exist in the ELF file.

## BSS section

The BSS rule begins:

~~~text
.bss (NOLOAD) : ALIGN(4K) {
    *(.bss .bss.*)
    *(COMMON)
~~~

This creates runtime address space for zero-initialized state and assigns it to the data PHDR.

## NOLOAD

NOLOAD is an output-section type that indicates there is no ordinary file payload to load for that section in the same sense as initialized data.

For ChrisOS, BSS still consumes runtime memory.

The important relationship is:

~~~text
memory extent
>
file-backed extent
~~~

which becomes reflected in the load segment through p_memsz relative to p_filesz.

## NOLOAD does not mean absent

The BSS section contains real runtime addresses.

It can contain:

- zero-initialized globals;
- COMMON symbols;
- stack reservation;
- alignment gaps.

A native linker must track this memory extent even if it writes no corresponding bytes into kernel.elf.

## COMMON

The pattern:

~~~text
*(COMMON)
~~~

collects common symbols into the BSS policy.

Common symbols historically represent tentative definitions.

Even if a particular compiler configuration rarely emits them, including COMMON makes the production policy explicit.

## Aligning the stack reservation

Inside BSS:

~~~text
. = ALIGN(16);
__stack_bottom = .;
~~~

The stack reservation begins at a 16-byte-aligned address.

System V AMD64 calling conventions rely on 16-byte stack-alignment discipline at call boundaries.

The linker provides a suitable base interval, while entry code remains responsible for setting RSP correctly.

## One-MiB reservation

The line:

~~~text
. += 1024K;
~~~

advances the location counter exactly one MiB.

No input section causes this growth.

The script itself synthesizes zero-filled memory extent.

This is a feature current ChrisLd does not yet reproduce for the production kernel.

## Stack boundaries

The resulting symbols satisfy:

~~~text
__stack_top - __stack_bottom = 1024 * 1024
~~~

before final page alignment.

The interval is conceptually:

~~~text
[__stack_bottom, __stack_top)
~~~

and the x86-64 stack grows downward from a high address within such an interval.

## Reserving memory is not switching stacks

The linker only creates an address-space reservation and symbols.

It does not modify RSP.

The bootloader provides an initial stack.

Kernel entry/runtime code determines when a ChrisOS-owned stack is used.

This distinction was also important in the boot-information chapter.

## Final page alignment

After defining stack top:

~~~text
. = ALIGN(4K);
__kernel_end = .;
~~~

The final kernel boundary is page-aligned.

This makes the kernel extent convenient for page-granular reservation.

## __kernel_end semantics

__kernel_end is after:

- requests;
- text;
- rodata;
- data;
- BSS;
- stack reservation;
- final alignment.

It is therefore a runtime layout boundary, not merely the last file byte of kernel.elf.

## File size is not kernel memory size

Because BSS and linker-synthesized stack memory do not require equal file payload:

~~~text
kernel.elf bytes
!=
runtime kernel memory extent
~~~

Memory management must not reserve the kernel based only on file length.

## /DISCARD/

ChrisOS ends with:

~~~text
/DISCARD/ : {
    *(.eh_frame*)
    *(.note*)
    *(.comment*)
}
~~~

/DISCARD/ explicitly removes matching input sections from the output.

This is deterministic script policy, not reachability analysis.

## .eh_frame

.eh_frame usually stores unwind information.

ChrisOS currently does not depend on a hosted exception/unwind runtime.

The script removes it.

If the project later implements a kernel unwinder based on standard unwind metadata, this policy must change deliberately.

## .note

.note sections can carry build metadata, ABI notes or architecture properties.

The current wildcard discards all .note* sections.

That broad rule should be revisited if future build-id or security-property notes become useful.

## .comment

.comment commonly carries compiler identification text.

It is not required to execute the kernel.

Discarding it removes non-runtime compiler metadata.

## /DISCARD/ versus section garbage collection

These are different mechanisms.

~~~text
/DISCARD/
    explicit script removal

section GC
    reachability-based elimination

KEEP
    protects matched input sections from GC
~~~

A section matched by /DISCARD/ is intentionally excluded even if it might otherwise be reachable.

## VMA

An allocatable output section has a Virtual Memory Address.

The VMA is the address used when the program runs.

ChrisOS begins its VMA layout at:

~~~text
0xffffffff80000000
~~~

and continues upward through output sections.

## LMA

GNU ld also models the Load Memory Address.

VMA and LMA can differ.

A classic embedded example is:

~~~text
initialized data
    stored in ROM at load time
    copied to RAM for runtime
~~~

The ROM address is the LMA and the RAM runtime address is the VMA.

## AT and AT>

GNU ld can specify a load address with:

~~~text
AT(expression)
~~~

or a load region with:

~~~text
AT>region
~~~

ChrisOS does not currently use either form.

Therefore linker.ld does not explicitly implement a ROM-to-RAM split address model.

## Current VMA/LMA model

Because ChrisOS does not specify AT or AT>, its script leaves load-address behavior to GNU ld's normal heuristics for the declared output.

The key project requirement is the higher-half VMA plus ELF program-header structure consumed by Limine.

This should not be confused with the physical RAM address at which Limine stores the image.

## Limine physical placement is a different layer

The layers are:

~~~text
linker:
    chooses virtual layout

ELF:
    encodes loadable segments

Limine:
    allocates physical backing
    constructs mappings

CPU:
    executes virtual addresses
~~~

The actual physical placement is bootloader policy, not the numeric higher-half linker location.

## MEMORY

GNU ld supports named memory regions:

~~~text
MEMORY {
    ROM (...) : ORIGIN = ..., LENGTH = ...
    RAM (...) : ORIGIN = ..., LENGTH = ...
}
~~~

Output sections can be assigned to those regions.

ChrisOS does not use MEMORY today.

## Why ChrisOS does not need MEMORY currently

The current target is a Limine-loaded general x86-64 kernel, not a fixed microcontroller ROM/RAM map.

Limine is responsible for locating the executable in physical memory.

The kernel script primarily needs a virtual layout and program-header policy.

A future platform with fixed memory regions might benefit from MEMORY.

## ADDR and SIZEOF

GNU ld expressions can query output sections using mechanisms such as:

~~~text
ADDR(.text)
SIZEOF(.text)
~~~

These are useful when later addresses depend on earlier output sections.

Current linker.ld does not use them.

## LOADADDR

LOADADDR queries the LMA of an output section.

It becomes useful when VMA and LMA differ.

Current ChrisOS has no explicit split LMA design and therefore has no need for LOADADDR in linker.ld.

## PROVIDE

GNU ld can conditionally provide symbols.

This is useful for defaults that may already be defined elsewhere.

ChrisOS instead uses unconditional assignments for its current synthetic symbols.

That makes the kernel and stack boundaries entirely script-controlled.

## ASSERT

GNU ld can evaluate assertions and fail the link.

Current linker.ld contains no ASSERT.

Potential future invariants include:

- expected stack size;
- canonical higher-half bounds;
- mandatory request-section presence;
- section alignment;
- maximum image size.

Today these are checked through source structure, external tools and CI rather than script assertions.

## SORT

GNU ld supports ordering wildcard matches explicitly.

ChrisOS does not use SORT.

Its critical ordering is expressed at the category level by listing request-start, request body and request-end patterns in sequence.

## SUBALIGN

SUBALIGN can override alignment requirements of input subsections inside an output section.

ChrisOS does not use it.

Input alignment requirements remain in effect while major output sections receive 4-KiB alignment.

## ALIGN_WITH_INPUT

GNU ld can preserve VMA/LMA delta behavior through an output section with ALIGN_WITH_INPUT.

ChrisOS does not use this because it does not construct a split VMA/LMA image in linker.ld.

## Fill patterns

GNU ld can select fill patterns for gaps.

ChrisOS does not define a custom FILL policy.

No kernel code should assume a particular file padding byte unless the produced ELF is inspected or the policy is made explicit.

## PHDR assignment inheritance

GNU ld can carry PHDR assignment to later allocatable sections depending on script structure.

ChrisOS explicitly assigns every major allocatable output section:

~~~text
:requests
:text
:data
~~~

This removes ambiguity and makes review easier.

## Why three program headers

The design partitions the initial image by purpose and permissions:

~~~text
boot metadata     RW
code/constants    RX
mutable state     RW
~~~

One universal segment would couple code and writable data permissions.

Three program headers let the bootloader establish a cleaner protection model.

## Why requests have their own segment

Limine request data is writable and could theoretically share data.

ChrisOS keeps it separate to provide:

- clear protocol identity;
- predictable placement;
- independent inspection;
- straightforward PHDR verification;
- reduced coupling to ordinary mutable state.

This is an architectural choice.

## Linker script and security

The script influences security properties:

- W^X;
- zero initialization;
- code/data separation;
- explicit metadata retention;
- exclusion of unwanted sections;
- alignment;
- stack extent.

A linker-script review is therefore part of a kernel security review.

## Linker script and memory management

The script defines the linked virtual extent.

The bootloader determines physical backing.

PMM and MM eventually need both forms of information:

~~~text
linked boundaries
+
bootloader memory/load information
~~~

This is why linker symbols and boot-information normalization are complementary.

## Linker script and higher-half execution

The relationship is:

~~~text
linker.ld:
    code is assigned high virtual addresses

Limine:
    those virtual addresses are mapped

ELF entry:
    contains high virtual kstart address

CPU:
    begins executing mapped kstart
~~~

If the linker and bootloader disagree, entry fails immediately.

## Compiler code model interaction

The makefile uses:

~~~text
-mcmodel=kernel
-fno-pic
-fno-pie
~~~

while the linker fixes the base at:

~~~text
0xffffffff80000000
~~~

These choices are coordinated.

Moving the kernel layout independently of compiler code-model assumptions can make generated relocations invalid or out of range.

## Linker-created symbols and relocations

Kernel object code can reference symbols such as __kernel_start.

Those references become relocations.

The linker resolves them even though no object file defines the symbol.

Therefore a native linker replacement needs a synthetic-symbol table in addition to symbols read from objects.

## Current ChrisLd

ChrisLd does not parse kernel/metal/linker.ld.

Its layout is hard-coded in C.

Current behavior includes:

- pack text;
- place rodata after text;
- emit RX load segment;
- optionally emit RW data/BSS segment;
- resolve selected x86-64 relocations;
- choose kstart or main as entry;
- validate basic ELF properties.

This is real static-link behavior, but not production ChrisOS layout parity.

## General script parser versus explicit kernel policy

ChrisLd has two broad implementation paths.

### Implement a linker-script subset

Parse enough GNU ld syntax to consume the current script:

- OUTPUT_FORMAT;
- OUTPUT_ARCH;
- ENTRY;
- PHDRS;
- SECTIONS;
- wildcard selectors;
- symbol assignments;
- dot arithmetic;
- ALIGN;
- KEEP;
- NOLOAD;
- /DISCARD/.

Advantages:

- linker policy remains in one file;
- easier host/native comparison;
- less risk of long-term policy drift.

Costs:

- parser and evaluator complexity.

### Implement kernel-specific layout structures

Encode the production layout directly in ChrisLd data structures.

Advantages:

- smaller bootstrap step;
- easier initial implementation.

Costs:

- duplicated policy;
- risk of divergence;
- weaker reuse for other executable types.

The project should avoid two silently different definitions of kernel layout over the long term.

## Minimal native parity requirements

Even without a general GNU ld parser, a kernel-capable ChrisLd must reproduce:

~~~text
ELF64 x86-64
ENTRY(kstart)

higher-half base
__kernel_start

Limine request section identity
request start/body/end ordering
retention semantics
RW requests PT_LOAD

text and text.* collection
RX text PT_LOAD

rodata and rodata.* collection
same intended protection policy

data and data.* collection
RW data PT_LOAD

BSS and bss.* collection
zero-fill semantics
COMMON-equivalent semantics if emitted

16-byte stack boundary
1 MiB linker-created stack extent
__stack_bottom
__stack_top

page-aligned __kernel_end

discard/ignore unsupported metadata
~~~

## ChrisO lacks a current request-section class

ChrisO v2 defines:

~~~text
TEXT
RODATA
DATA
BSS
~~~

It does not define a dedicated Limine request section class.

Therefore production parity requires more than changing the final program-header writer.

The native front end/object format must preserve special section identity.

## Native section-attribute pipeline

For Limine compatibility, the native toolchain needs:

~~~text
source section attribute
    |
KCC recognizes it
    |
ChrisO preserves section identity
    |
ChrisLd groups it correctly
    |
request segment emitted
~~~

Losing the special section at any point makes the final kernel incompatible with the current boot protocol.

## KEEP parity

ChrisLd currently does not implement dead-section elimination.

That means request data would not be discarded by a GC pass today.

However, production architecture should still represent retention explicitly.

If garbage collection is introduced later, request sections must remain roots.

## BSS parity

ChrisLd already has object BSS accounting.

The production linker script adds something different:

~~~text
linker-created zero-fill extent
~~~

through the one-MiB stack reservation.

ChrisLd therefore needs a mechanism for synthetic memory reservations independent of object BSS size.

## Synthetic-symbol parity

Current ChrisLd symbols originate from ChrisO objects.

Production parity also requires script-generated symbols:

~~~text
__kernel_start
__stack_bottom
__stack_top
__kernel_end
~~~

They must be available during relocation resolution.

## Assignment timing

The value of a linker symbol depends on the exact point at which it is assigned.

~~~text
__kernel_start
    before request section

__stack_bottom
    after object BSS and ALIGN(16)

__stack_top
    after adding 1 MiB

__kernel_end
    after final page alignment
~~~

A native implementation must preserve this temporal layout semantics.

## Small useful expression subset

The current script needs only a modest subset of the full GNU expression language:

~~~text
dot = constant
symbol = dot
dot = ALIGN(power_of_two)
dot += constant
~~~

This makes a first script interpreter much smaller than implementing every GNU ld feature.

## Practical ChrisLd migration path

A staged path is:

### Stage 1

Introduce explicit output-layout structures:

~~~text
program headers
output sections
synthetic symbols
zero-fill reservations
retention rules
discard rules
~~~

### Stage 2

Extend ChrisO/KCC/ChrisAsm so special named sections can survive compilation.

### Stage 3

Represent linker-created BSS/NOLOAD reservations.

### Stage 4

Create synthetic linker symbols and allow relocations against them.

### Stage 5

Emit three production-equivalent PT_LOAD segments.

### Stage 6

Compare semantic output against host ld.

### Stage 7

Optionally parse the current linker.ld subset so policy is no longer duplicated.

## Differential verification

A host-versus-native link comparison should inspect:

- ELF class;
- architecture;
- entry;
- program-header count;
- segment flags;
- segment ordering;
- virtual addresses;
- file and memory sizes;
- required synthetic symbols;
- request marker ordering;
- BSS extent;
- stack reservation;
- kernel end.

Semantic equivalence matters more than byte-for-byte identity.

## readelf gate

A future CI stage can inspect the actual kernel:

~~~text
readelf -h kernel.elf
readelf -l kernel.elf
readelf -S kernel.elf
readelf -s kernel.elf
~~~

This can verify the output rather than only source policy.

## Link-map gate

GNU ld can produce a link map.

Tracking it would allow:

- section size regressions;
- symbol address changes;
- object contribution analysis;
- host/native layout comparison;
- early detection of accidental growth.

This becomes increasingly valuable as ChrisOS expands.

## Current linker-script invariants

At revision da3df29, the production source requires all of the following:

1. ELF64 x86-64 output format.
2. x86-64 output architecture.
3. kstart entry symbol.
4. higher-half virtual start at 0xffffffff80000000.
5. __kernel_start at the initial location.
6. three named PT_LOAD program headers.
7. requests RW.
8. text RX.
9. data RW.
10. no declared W+X PT_LOAD.
11. page-aligned request output section.
12. ordered request start/body/end inputs.
13. KEEP around all request categories.
14. page-aligned .text.
15. collection of .text and .text.*.
16. page-aligned .rodata.
17. collection of .rodata and .rodata.*.
18. rodata assigned to the text PHDR.
19. page-aligned .data.
20. collection of .data and .data.*.
21. page-aligned NOLOAD .bss.
22. collection of .bss and .bss.*.
23. COMMON collected into BSS.
24. stack bottom aligned to 16 bytes.
25. exactly 1024 KiB reserved for stack extent.
26. __stack_top after the reservation.
27. final location aligned to 4 KiB.
28. __kernel_end after final alignment.
29. .eh_frame* discarded.
30. .note* discarded.
31. .comment* discarded.

The checker added with this chapter encodes these contracts.

## Features not currently used

Current linker.ld does not use:

- MEMORY;
- AT;
- AT>;
- explicit separate LMA;
- LOADADDR;
- PROVIDE;
- ASSERT;
- SORT;
- SUBALIGN;
- ALIGN_WITH_INPUT;
- OVERLAY;
- custom FILL;
- PIE/dynamic-link sections.

These are GNU ld capabilities, not current ChrisOS implementation facts.

## Reproducible checker

scripts/check_linker_script_examples.py validates:

- the entire production linker.ld source contract;
- location-counter examples;
- 4-KiB and 16-byte alignment;
- one-MiB reservation arithmetic;
- PT_LOAD permission arithmetic;
- request/text/data assignments;
- request KEEP order;
- NOLOAD BSS;
- discard patterns;
- absence of MEMORY and AT policy;
- current ChrisLd absence of Limine request handling and production synthetic symbols.

It is a source-contract and arithmetic checker.

It does not replace final ELF inspection.

## Validation boundary

This chapter is reconciled with:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

and with the current GNU Binutils linker-script documentation.

Generic GNU ld features are clearly separated from features actually used by ChrisOS.

Run:

~~~text
python scripts/check_linker_script_examples.py --source .source
~~~

## Review triggers

Review this chapter when:

- kernel/metal/linker.ld changes;
- the kernel virtual base changes;
- PHDR count or permissions change;
- rodata becomes R-only;
- stack size changes;
- linker-generated symbols change;
- new boot metadata sections appear;
- section garbage collection is enabled;
- MEMORY or AT is introduced;
- ChrisO gains generic/special named sections;
- ChrisLd implements production kernel layout;
- ChrisLd begins parsing linker scripts;
- a native-linked kernel boots.

## Primary references

- GNU Binutils ld manual, Linker Scripts.
- System V ABI, ELF program-header model.
- ChrisOS kernel/metal/linker.ld.
- ChrisOS makefile, ChrisO and ChrisLd sources listed in front matter.
