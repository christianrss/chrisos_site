---
id: chrisasm
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/kcc/kcc.c
  - tools/test_chrisasm.c
symbols:
  - chrisasm_assemble
  - add_sym
  - add_reloc
  - local_find
  - local_define
  - add_fix
  - patch_fixups
  - emit_disp_reloc
  - emit_call_or_jmp
  - emit_local_branch
  - parse_mem
  - parse_line
  - publish_secs
depends_on:
  - native-toolchain
  - machine-code
  - x86-instruction-encoding
  - calling-conventions
related:
  - kcc
  - chriso
  - chrisld
---

# ChrisAsm

## Scope

ChrisAsm is the native x86-64 assembler used by the experimental ChrisOS toolchain. It accepts a deliberately limited textual assembly language and produces a ChrisO object image containing section bytes, symbols and relocations.

The current path is:

    assembly text
        -> line parser
        -> x86-64 encoder
        -> local-label fixups
        -> ChrisO sections, symbols and relocations

KCC emits assembly in the syntax ChrisAsm accepts, so ChrisAsm is the machine-code boundary between the compiler front end and the object/linker stages. It is not a wrapper around GNU as, NASM, LLVM MC or another external assembler.

ChrisAsm should therefore be understood as a project-specific assembler with a controlled instruction and directive profile, not as a general x86-64 assembler.

## Public interface

The public header exposes one function:

    int chrisasm_assemble(const char *src, ChrisoImage *out);

The caller supplies a null-terminated assembly source string and a destination ChrisO image. The function returns zero on success and minus one on failure.

There is currently no public diagnostic object, source-position structure or textual error string. A failed parse, unsupported instruction, capacity overflow, duplicate symbol or unresolved local fixup all collapse to the same return value.

This keeps the interface small but makes error localization dependent on higher-level tooling or source minimization.

## Global assembler state and reentrancy

The implementation uses process-global mutable state:

- three 64 KiB byte buffers for text, rodata and data;
- four section-length counters, including BSS size;
- the current section selector;
- an overflow flag;
- a local-binding flag;
- a table of local labels;
- a table of pending same-section fixups.

The principal fixed limits are:

| Resource | Limit |
| --- | ---: |
| text bytes | 65,536 |
| rodata bytes | 65,536 |
| data bytes | 65,536 |
| local labels | 1,024 |
| local branch fixups | 4,096 |
| input line buffer | 512 bytes |
| ChrisO symbols | 256 |
| ChrisO relocations | 512 |

Because these buffers and counters are global, ChrisAsm is not reentrant. Two concurrent calls to chrisasm_assemble in the same address space would share encoding state and can corrupt each other.

A future per-assembly context would be required for safe parallel assembly.

## Assembly pass structure

chrisasm_assemble performs a single source scan by lines.

At entry it:

1. initializes the output ChrisO image;
2. clears overflow and local-fixup state;
3. selects the text section;
4. resets all section lengths;
5. copies characters into a 512-byte line buffer;
6. invokes parse_line for each completed line;
7. resolves deferred local-label fixups;
8. copies the generated section bytes into newly allocated output buffers.

This is not a traditional multi-pass assembler over a token stream and expression tree. ChrisAsm encodes instructions while reading lines and uses a bounded deferred-fixup table only where a local target has not yet been defined.

The line-oriented architecture is simple and suitable for KCC-generated assembly, but it is also a syntax constraint.

## Line-length behavior

The line buffer has space for 511 source characters plus the terminator.

When a line exceeds that capacity, additional characters are ignored until the newline. The implementation does not currently turn that truncation into an explicit error.

This means very long generated or handwritten assembly lines can be silently shortened before parse_line sees them.

KCC normally emits compact instruction lines, so this is not expected in ordinary compiler output, but it is a real parser boundary and should eventually be changed to fail closed on overflow.

## Sections

ChrisAsm recognizes four logical sections:

| Directive | ChrisO section | Stored bytes |
| --- | --- | --- |
| .text | CHRISO_SEC_TEXT | yes |
| .rodata | CHRISO_SEC_RODATA | yes |
| .data | CHRISO_SEC_DATA | yes |
| .bss | CHRISO_SEC_BSS | size only |

The first three sections are backed by fixed 64 KiB assembler buffers.

BSS is different. .zero or .skip in BSS increases the BSS section length without emitting bytes. When the final ChrisO image is published, the BSS pointer remains null while its size records the reserved address-space requirement.

This distinction is preserved by the ChrisO serializer and later linker.

## Data directives

The current directive profile includes:

- .global and global;
- .local;
- .extern and extern;
- .zero and .skip;
- .ascii;
- .asciz;
- .byte;
- .quad;
- section directives for text, rodata, data and BSS.

.global is accepted but does not maintain a separate export table. Ordinary non-local labels are already emitted as global ChrisO symbols.

.local affects the binding of the next label definition.

.extern immediately creates or reuses an undefined function symbol.

String directives use a bounded 256-byte temporary literal buffer. Escape handling recognizes newline, carriage return and zero escapes. This is not a complete assembler string-escape language.

## Symbols and bindings

ChrisAsm emits ChrisO symbols through add_sym.

A symbol records:

- a fixed 64-byte name field;
- section index;
- section-relative offset;
- size;
- binding;
- kind.

Bindings used by the assembler are local, global and undefined.

A newly referenced external target can be created as undefined and later upgraded when its definition is encountered. Defining an already defined non-undefined symbol is rejected.

Labels in the text section are classified as function symbols. Labels in other sections are classified as object symbols.

This classification is intentionally simple. There is no complete ELF symbol model at the assembler layer.

## Why .L labels are special

Compiler-generated assembly can contain many internal labels. Storing every local control-flow label in the ChrisO symbol table would quickly consume the object format's 256-symbol limit.

ChrisAsm therefore treats names beginning with .L specially.

Same-section .L labels are stored in an assembler-private table rather than automatically becoming ChrisO symbols. Forward references are recorded in a private fixup table.

After the source has been parsed, patch_fixups computes each 32-bit relative displacement directly:

    displacement = target_offset - (relocation_field_offset + 4)

The assembler then writes the displacement into the generated section bytes.

This avoids unnecessary linker work for ordinary compiler-internal branches and preserves symbol-table capacity for externally meaningful names.

## Cross-section and external control flow

A local-looking label cannot always be resolved privately.

If a branch target is defined in another section, or if the target must survive into the linker boundary, ChrisAsm falls back to a real symbol plus ChrisO relocation.

Calls, jumps and conditional branches to unresolved external symbols use PC-relative relocations.

The call/jump path emits a placeholder displacement and creates an R_X86_64_PLT32 relocation with addend -4.

The -4 addend reflects x86-64 PC-relative semantics: the relocation field contains a displacement relative to the address immediately after the four-byte field.

The host test explicitly verifies this behavior for:

    call foo

It requires exactly one relocation, type R_X86_64_PLT32, addend -4, and an undefined symbol named foo.

## RIP-relative data references

The memory parser supports the project syntax:

    [rel symbol]

For such an operand, ChrisAsm encodes a RIP-relative ModR/M form, writes a zero 32-bit displacement placeholder and creates an R_X86_64_PC32 relocation with addend -4.

The referenced symbol is created as an undefined object symbol when necessary.

This is the principal mechanism used for position-relative references to globals generated by KCC.

## Register-based memory operands

The memory parser also accepts a simpler base-register form:

    [register]
    [register + displacement]
    [register - displacement]

The displacement is an integer literal. There is no general effective-address expression parser with arbitrary base plus index times scale plus symbol arithmetic.

emit_mem_modrm chooses ModR/M displacement width according to the value:

- no displacement when possible;
- signed 8-bit displacement for values in the -128 to 127 range;
- otherwise a 32-bit displacement.

RSP/R12 bases receive the required SIB byte. RBP/R13 with no explicit displacement are forced into a displacement form because ModR/M encoding zero would otherwise mean a different addressing mode.

## Encoding model

ChrisAsm directly emits x86-64 bytes.

The implementation constructs:

- REX prefixes;
- opcode bytes;
- ModR/M bytes;
- SIB bytes where necessary;
- immediates and displacements;
- relocation placeholders.

The encoder is explicit C code rather than a generated instruction table.

That makes the supported subset inspectable, but it also means every additional instruction form requires implementation and validation.

## Supported instruction families

The current parser contains forms for the operations needed by KCC and the native-toolchain path. They include, among others:

- mov and movzx;
- lea;
- add, sub and imul;
- div;
- xor, or, and, not;
- cmp and test;
- shl;
- push and pop;
- call and ret;
- jmp and conditional branches;
- sete;
- syscall;
- cli, sti, hlt and pause;
- in and out;
- lretq and iretq;
- str and ltr;
- invlpg;
- lock-prefixed supported operations.

Conditional branches currently recognized include equal/not-equal, unsigned comparisons and signed comparisons.

This list must not be interpreted as complete x86-64 coverage. Forms are accepted only where parse_line implements the exact operand pattern.

## Register profile

ChrisAsm contains project-local helpers for mapping x86-64 register spellings to encoding numbers and widths.

The encoder supports the general-purpose register forms needed by the current compiler, including extended registers that require REX bits.

The host test verifies one such case directly: push r8 must encode with the 0x41 REX prefix followed by opcode 0x50.

SIMD, x87 and broad AVX/AVX-512 encoding are not part of the current assembler profile.

## Local fixup complexity

local_find performs a linear scan over the local-label table.

For L local labels, one lookup is O(L). patch_fixups performs one lookup for each pending fixup, so the worst-case fixup phase is O(F times L), where F is the number of deferred fixups.

With current limits of 4,096 fixups and 1,024 local labels, the bound is finite but not asymptotically efficient.

A hash table or sorted symbol structure would improve scaling if assembly units become much larger.

The current design favors simple fixed-capacity state and predictable allocation behavior.

## Section publication and ownership

Encoding occurs in static assembler buffers.

publish_secs converts those temporary buffers into the output ChrisO image. For each non-empty text, rodata or data section it allocates exactly the generated size and copies the bytes.

Host builds use malloc. Freestanding builds use kmalloc.

BSS receives no allocation.

The result therefore owns dynamically allocated section storage for the materialized sections. Consumers must respect the lifecycle expected by the surrounding toolchain. ChrisAsm itself does not expose a matching public destroy function.

This ownership asymmetry is another area where a future object-lifecycle API would improve robustness.

## Failure behavior

ChrisAsm rejects unsupported or malformed input by returning -1.

Failure sources include:

- unknown mnemonics;
- unsupported operand forms;
- duplicate symbol definitions;
- invalid registers;
- exceeded symbol or relocation limits;
- section byte overflow;
- local-label table overflow;
- local-fixup overflow;
- unresolved or cross-section private fixups that cannot be represented by the selected path;
- allocation failure while publishing sections.

The parser generally fails closed for an unrecognized operation.

The principal exception is overlong source lines, which are truncated rather than rejected.

## Validation evidence

tools/test_chrisasm.c provides executable host evidence for several important contracts.

It verifies that:

1. a small function containing mov rax, 42 and ret assembles;
2. the produced text starts with a 64-bit REX prefix;
3. an unknown mnemonic is rejected;
4. an unresolved call produces a PLT32 relocation with addend -4;
5. the relocation points at an undefined symbol named foo;
6. push r8 emits the expected extended-register encoding.

These tests establish real behavior for the tested forms. They do not establish full correctness of every parse_line branch or every x86-64 encoding combination.

## Security and privilege boundary

ChrisAsm can encode privileged instructions such as cli, sti, hlt, ltr and invlpg.

The assembler does not enforce execution privilege. It only translates text into bytes.

Privilege validity is a runtime property of where the generated code executes. Kernel tooling must therefore treat assembled code as native executable content with the same trust implications as code produced by any other compiler or assembler.

ChrisAsm is not a sandbox.

## Current limitations

The most important current limitations are:

- process-global non-reentrant state;
- fixed 64 KiB materialized section limits;
- 256-symbol and 512-relocation ChrisO limits;
- 1,024 private local labels;
- 4,096 private local fixups;
- no rich diagnostics;
- silent truncation of overlong source lines;
- project-specific directive grammar;
- incomplete x86-64 instruction coverage;
- no general assembler expression evaluator;
- no general base-index-scale effective-address grammar;
- no SIMD/x87/AVX assembler surface;
- manual instruction-form implementation.

These are implementation boundaries, not defects in x86-64 itself.

## Roadmap boundary

A more complete ChrisAsm can evolve in several independent directions:

- replace global state with an explicit assembler context;
- add structured diagnostics with line and column information;
- reject line-buffer overflow explicitly;
- replace linear local-symbol lookup when larger translation units require it;
- expand instruction-form coverage from a table-driven description;
- add an expression engine for constants, symbols and relocatable arithmetic;
- define explicit object-image destruction and ownership rules;
- increase or dynamically allocate section, symbol and relocation capacity.

None of those future directions should be read as current behavior.

## Revision provenance

This chapter documents ChrisAsm as observed in ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

The primary implementation authority is compiler/chrisasm/chrisasm.c with the public boundary in compiler/chrisasm/chrisasm.h. ChrisO structure definitions come from compiler/chrisld/chriso.h, and tools/test_chrisasm.c is the cited executable host evidence.
