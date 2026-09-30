---
id: native-codegen
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.c
  - compiler/kcc/kcc.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - kernel/tools/native_link.c
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chriso.c
  - tools/test_chrisld.c
  - tools/test_native_link.c
symbols:
  - kcc_compile_named
  - asm_line
  - asm_cat
  - asm_mov_imm
  - alloc_slot
  - temp_slot
  - load_val
  - store_val
  - gen_addr
  - parse_args
  - apply_bin
  - epilogue
  - chrisasm_assemble
  - add_sym
  - add_reloc
  - ChrisoImage
  - ChrisoSym
  - ChrisoRel
  - chriso_write
  - chriso_read
  - chrisld_link_objects
  - resolve_sym
  - apply_one
depends_on:
  - intermediate-representation
  - semantic-analysis
  - x86-instruction-encoding
  - elf-linking
related:
  - calling-conventions
  - native-toolchain
  - kcc
  - chrisasm
  - chriso
  - chrisld
---

# Native code generation

## Scope

Native code generation converts language semantics into instructions and data structures that execute directly on the target processor rather than through the CLVM interpreter.

In current ChrisOS, the native C-like compilation path is:

    C-like source
        ->
    KCC preprocessing + parsing + semantic actions
        ->
    textual x86-64 assembly
        ->
    ChrisAsm
        ->
    ChrisO object image
        ->
    ChrisLd
        ->
    ELF64 executable image

KCC does not currently lower through a persistent target-independent machine IR. Parsing and native emission are coupled. ChrisAsm then performs actual x86-64 instruction encoding, and ChrisLd performs section placement, symbol resolution and relocation.

This chapter documents that native path. CLVM bytecode lowering belongs to the ChrisC/CLVM chapters, while runtime JIT translation is a separate mechanism.

![Native code generation in ChrisOS](../../assets/diagrams/native-codegen-en.svg)

## Code generation boundary

There are two distinct code-generation boundaries.

KCC translates source-level operations into textual assembly instructions.

ChrisAsm translates those textual instructions into exact x86-64 bytes and relocation records.

This split is important.

KCC needs to know which registers and instruction families express an operation, but it does not itself encode REX prefixes, ModRM bytes, SIB bytes or immediate fields.

ChrisAsm owns those encoding details.

The practical backend pipeline is therefore:

    semantic value
        ->
    assembly spelling
        ->
    machine encoding
        ->
    relocatable object state
        ->
    linked executable

## KCC emission model

KCC emits into a global assembly text buffer.

Helpers such as:

    asm_line(...)
    asm_cat(...)
    asm_mov_imm(...)

append instruction text.

For example, asm_mov_imm writes a decimal immediate into a textual:

    mov register, immediate

form.

At the end of kcc_compile_named, KCC terminates the assembly buffer and calls:

    chrisasm_assemble(g_asm, out)

where out is a ChrisoImage.

If ChrisAsm rejects the translation, KCC reports a compile error.

Thus a successful KCC parse is not enough: generated assembly must also be accepted by the project assembler.

## RAX as the principal expression register

The current generator uses RAX as the primary value register for most expression evaluation.

Literal values are materialized into RAX.

Loads place values into RAX.

Arithmetic normally leaves its result in RAX.

Function results are expected in RAX by the generated call path.

When two values must coexist, KCC commonly saves one to a temporary frame slot, evaluates the other, moves it to RCX or another helper register, then reloads the first into RAX.

This is a simple accumulator-oriented strategy rather than a register-allocation algorithm.

## Temporary values and frame spills

save_rax allocates a temporary slot and stores RAX there.

Temporary slots begin in a separate negative-offset region below RBP.

Ordinary local storage is allocated by alloc_slot.

alloc_slot rounds each requested slot to at least eight bytes and to an eight-byte boundary. It rejects ordinary-frame growth beyond the configured 1536-byte local allocation budget.

Function entry currently reserves:

    sub rsp, 2048

after establishing RBP.

The compiler therefore reserves a fixed frame area large enough for locals and the temporary-spill region used by the current generator.

This design is straightforward and deterministic, but it produces more memory traffic than a backend with liveness analysis and register allocation.

## Local address model

frame_txt constructs addresses relative to RBP.

A local value may therefore appear as:

    [rbp-N]

Parameters beyond the register-argument subset are addressed at positive offsets:

    [rbp+16]
    [rbp+24]
    ...

gen_addr uses LEA for local addresses.

The use of a stable frame pointer simplifies local-variable addressing, temporary spills and debugging.

The cost is that RBP is permanently dedicated as a frame pointer in generated functions.

## Function prologue and epilogue

A normal KCC function definition emits a fixed prologue:

    push rbp
    mov rbp, rsp
    sub rsp, 2048

The epilogue helper emits:

    mov rsp, rbp
    pop rbp
    ret

This gives every generated function the same broad stack-frame shape regardless of actual local storage demand.

It avoids a later frame-size finalization pass.

A more advanced backend could compute exact frame size after analysis, but current KCC favors direct single-pass emission.

## Value loading

load_val bridges semantic Val state and machine instructions.

A value may be:

- an immediate;
- a local frame lvalue;
- a global lvalue;
- an indirect address lvalue;
- an array requiring decay to pointer;
- a function-like value.

Immediate values are rematerialized into RAX.

Local scalar values are loaded from RBP-relative memory.

Globals use RIP-relative syntax of the form:

    [rel symbol]

Indirect lvalues load through an address.

Small objects can use byte or 32-bit loads, while pointer and wider forms use 64-bit operations according to the current Type metadata.

This makes semantic size directly influence selected machine instruction width.

## Value stores

store_val performs the inverse translation.

For a local destination, RAX is written to the frame slot.

For globals, KCC emits symbol-relative stores.

For indirect destinations, the address is materialized and the result stored through it.

Widths again depend on Type.

The generator distinguishes byte-sized values from wider values and pointers.

Volatile global stores also interact with the local dead-store optimization state: volatile accesses clear or bypass optimization state so observable accesses are preserved.

## Address generation

gen_addr supports the location classes represented by Val.

For a local:

    lea rax, [rbp-offset]

For a global:

    lea rax, [rel symbol]

For an already-computed address lvalue, KCC reloads the stored address temporary.

Array indexing and structure field access build addresses by adding scaled offsets to a base.

Pointer increment/decrement uses pointee_size as the step.

The backend therefore relies on semantic analysis having already produced correct sizes and offsets.

## Binary arithmetic

apply_bin lowers many binary operations directly.

The general pattern is:

1. evaluate the left side;
2. save RAX into a temporary slot;
3. evaluate the right side;
4. move the right result into RCX;
5. reload the left into RAX;
6. emit the target instruction.

Examples include:

    add rax, rcx
    sub rax, rcx
    and rax, rcx
    or rax, rcx
    xor rax, rcx
    imul rax, rcx

Division uses RDX:RAX conventions explicitly.

The current generator clears RDX before unsigned division paths and uses div for the supported arithmetic profile.

This direct instruction selection is intentionally simple and does not pass through a target-selection DAG.

## Comparisons

Comparison operators emit:

    cmp rax, rcx

followed by a helper that converts the selected condition into a canonical boolean value.

set_flag creates local labels and emits branches that produce zero or one in RAX.

The result Type becomes boolean.

This is a branch-based materialization strategy rather than using the x86 SETcc family universally.

ChrisAsm does support selected instruction forms used by the generated assembly, but the high-level KCC path chooses the emitted sequence.

## Short-circuit control flow

Logical AND and OR cannot be emitted as ordinary arithmetic because the right expression may not execute.

KCC emits labels while parsing.

For &&, a zero left operand branches around right-side evaluation.

For ||, a nonzero left operand branches around the right side.

The final value is normalized to a boolean.

Ternary expressions are handled similarly with generated labels for the false branch and join point.

This is direct control-flow code generation. There is no later CFG lowering stage.

## Statements and labels

new_lab generates names such as:

    .L0
    .L1

Structured statements emit branches against those labels.

if, loops, break, continue and ternary expressions therefore become local assembly labels and conditional/unconditional jumps during parsing.

ChrisAsm treats .L labels specially as assembler-local labels. Same-section local branches are patched internally rather than consuming ordinary ChrisO symbol slots.

This matters because kernel files can contain more local labels than the finite ChrisO symbol table should carry.

## Function calls

The current call generator evaluates arguments before the call.

The first six integer/pointer argument positions are moved into:

    rdi
    rsi
    rdx
    rcx
    r8
    r9

Additional arguments are written into stack space prepared by the caller.

Direct calls emit:

    call symbol

Function-pointer calls load the target and emit:

    call rax

After a direct or indirect call, the result remains in RAX.

The exact calling convention and stack-layout contract are documented in the next chapter; here the important code-generation point is that call lowering is performed immediately from the parsed argument list.

## Function parameters

At function entry, KCC copies the first six incoming register parameters into local frame slots.

Later references to those parameters then use the same local-load machinery as ordinary locals.

Parameters after the first six are represented at positive RBP offsets beginning at 16 bytes from the frame pointer.

This simplifies expression code generation because most parameter reads are normalized into memory locations.

Again, the trade-off is additional memory traffic.

## Global objects

KCC also emits data declarations, not only instructions.

Global initialization is parsed into byte buffers according to Type size and aggregate layout.

The generated assembly selects sections and emits object bytes or zero-initialized storage as required by the current assembler syntax.

External declarations become undefined symbols rather than allocated storage.

Static/global identity is carried into assembly naming and later into ChrisO symbol bindings.

Native code generation therefore includes both executable text and object data layout.

## Inline assembly

The supported C subset includes selected inline-assembly forms.

KCC parses constrained forms and can emit instructions for operations needed by low-level kernel code, including port I/O and control/system operations.

This is not a general GCC-compatible inline-assembly implementation.

The parser recognizes a project-supported subset of constraints and templates.

Inline assembly crosses the normal semantic-to-instruction selector boundary: source text can request target-specific behavior directly.

## Atomic builtins

KCC has specialized lowering for selected synchronization builtins.

For example, compare-and-swap emits lock-prefixed cmpxchg with width selected from the pointer type.

Fetch/add paths use lock xadd.

These operations demonstrate why native codegen must preserve memory-width semantics accurately.

They also show that high-level builtin names can lower to instruction sequences that are not expressible as ordinary arithmetic source operators.

## ChrisAsm responsibility

ChrisAsm receives textual assembly and converts it into machine bytes.

It owns:

- register encoding;
- REX prefix emission;
- opcode bytes;
- ModRM/SIB construction;
- displacement encoding;
- immediate encoding;
- local-label fixups;
- symbol creation;
- relocation creation;
- section buffers.

This creates a clean boundary: KCC selects assembly semantics, while ChrisAsm performs binary encoding.

## Instruction encoding

ChrisAsm provides helpers for instruction families rather than delegating to an external assembler.

For example, register-immediate MOV emission writes a REX prefix, opcode and 64-bit immediate.

Memory operands construct ModRM and, when needed, SIB and displacement fields.

RIP-relative symbolic memory references emit a placeholder displacement plus a ChrisO relocation.

The assembler therefore implements the subset of x86-64 encoding required by the native ChrisOS toolchain.

It is not a full NASM/GAS replacement.

## Local fixups versus object relocations

Two unresolved-name mechanisms are distinct.

Assembler-local .L labels are tracked in internal local-label/fixup tables and patched when the assembly unit is complete.

External or object-visible symbols become ChrisoSym records.

References that cannot be finalized within the assembly unit become ChrisoRel records.

This separation prevents temporary internal branch labels from polluting the object symbol table.

## ChrisO object representation

ChrisoImage contains four logical sections:

    .text
    .rodata
    .data
    .bss

and fixed-capacity arrays of symbols and relocations.

A ChrisoSym records:

- name;
- section;
- offset;
- size;
- binding;
- kind.

A ChrisoRel records:

- section;
- offset;
- symbol index;
- addend;
- relocation type.

The current relocation vocabulary includes familiar x86-64 forms such as:

    R_X86_64_64
    R_X86_64_PC32
    R_X86_64_PLT32
    R_X86_64_32
    R_X86_64_32S

ChrisO is therefore a compact project object format carrying enough information for the native linker.

## RIP-relative references

When ChrisAsm encodes a RIP-relative symbolic memory operand, it writes a zero displacement and adds an R_X86_64_PC32 relocation with addend -4.

The linker later computes the final displacement from symbol address and relocation place.

Conceptually:

    disp32 = S + A - P

where:

- S is resolved symbol address;
- A is relocation addend;
- P is relocation place.

The linker checks the resulting value fits the required signed range before writing it.

## Symbol resolution

ChrisLd resolves symbols across multiple ChrisoImage objects.

A defined non-global symbol resolves within its own object.

Global symbols are searched across the object set.

Duplicate global definitions are rejected.

An undefined reference must find a compatible global definition or linking fails.

This is conventional static-linker behavior implemented in a small project-specific linker.

## Section packing

ChrisLd computes per-object offsets within each logical section.

Objects within a section are aligned to 16-byte boundaries after the first nonempty contribution.

Read-only data follows text in the executable/read-only region.

Data and BSS cause creation of a writable region.

BSS contributes memory size but does not need file bytes.

The final output is ELF64 with one or two loadable segments depending on whether writable state is present.

## Entry selection

During linking, ChrisLd first looks for a defined symbol named:

    kstart

If no kstart is found, it searches for:

    main

The selected symbol address becomes the ELF entry point.

If neither is found, the initial load address remains the default entry value in the current implementation.

Kernel builds therefore obtain kstart preference, while simpler native programs can enter at main.

## Relocation application

For every ChrisoRel, the linker determines:

- the relocation site's file offset;
- the runtime address of that place;
- the referenced symbol definition;
- the final symbol virtual address.

apply_one then writes the appropriate relocated value.

64-bit absolute relocation writes eight bytes.

PC32/PLT32 computes a signed relative displacement.

32/32S forms write a checked 32-bit value under the implementation's current constraints.

Unsupported relocation kinds cause linking to fail rather than silently producing an image.

## Failure containment

Native code generation is fail-fast across stages.

KCC can reject unsupported source or overflow of internal buffers.

ChrisAsm rejects malformed or unsupported assembly, section overflow, duplicate symbol definitions and fixup failures.

ChrisO readers validate magic, version, counts and total serialized size.

ChrisLd rejects duplicate globals, unresolved symbols, bad relocation indices, invalid relocation sites and out-of-range relocation values.

A successful source parse therefore does not imply a successful executable image; each later boundary validates its own representation.

## Performance characteristics

KCC avoids a large optimizer and intermediate machine graph, so compile-time overhead is low and data structures are simple.

However, generated code often spills expression values to frame slots and reloads them.

Every function reserves a fixed 2048-byte stack frame.

The backend does not currently perform graph-coloring or linear-scan register allocation, global liveness analysis, instruction scheduling or peephole optimization as a separate pass framework.

ChrisAsm performs direct encoding in essentially linear time over assembly lines, with bounded local symbol/fixup tables.

ChrisLd performs object packing plus symbol and relocation scans; its simple global-symbol search can be quadratic in worst-case object/symbol counts but current fixed limits keep the implementation bounded.

## Validation evidence

tools/test_kcc.c compiles focused snippets and real kernel sources. It checks generated assembly properties, volatile behavior, structures, pointer operations, functions and linked object behavior.

tools/test_chrisasm.c exercises native assembly encoding and object creation.

tools/test_chriso.c checks object serialization and parsing.

tools/test_chrisld.c validates linking, symbols and relocations.

tools/test_native_link.c exercises the higher-level native link path.

The documentation CI also verifies instruction and register contracts against current source.

These tests establish the active path from KCC through ChrisO and ELF, but they do not prove that KCC is a complete optimizing C compiler.

## Current limitations

At the documented revision:

- native code generation targets x86-64 only;
- KCC emits assembly while parsing rather than from a target-independent IR;
- RAX is used as a primary accumulator and many intermediate values spill to memory;
- there is no general register allocator;
- every generated function reserves a fixed 2048-byte frame;
- ordinary local allocation is bounded;
- floating-point native value operations remain outside the supported KCC subset;
- the assembler supports the project-required x86-64 subset rather than the complete ISA;
- ChrisO symbol and relocation tables have fixed capacities;
- optimization is mostly local and syntax-directed;
- inline assembly supports only selected forms;
- the linker implements a focused static-link model rather than a complete ELF linker feature set.

## Roadmap boundary

A more advanced native backend could introduce:

- a typed machine-independent IR;
- explicit basic blocks and liveness;
- instruction selection from IR patterns;
- virtual registers;
- linear-scan or graph-coloring register allocation;
- exact frame-size computation;
- ABI-aware tail calls;
- peephole and machine optimization passes;
- richer floating/SIMD lowering;
- unwind metadata;
- debug information;
- additional target architectures;
- broader relocation and ELF support.

These items remain roadmap until corresponding implementation and validation exist.

## Source map and revision

KCC emission is concentrated in compiler/kcc/kcc.c around asm_line, asm_cat, asm_mov_imm, load_val, store_val, gen_addr, parse_args, apply_bin, statement lowering, alloc_slot, temp_slot and epilogue.

Binary instruction encoding, local-label fixups, symbols and relocations live in compiler/chrisasm/chrisasm.c.

The native object format is defined by compiler/chrisld/chriso.h and serialized in chriso.c.

Final section layout, symbol resolution, relocation application and ELF construction are implemented in compiler/chrisld/chrisld.c.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
