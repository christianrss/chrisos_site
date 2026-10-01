---
id: kcc
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.h
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - kernel/metal/kcc_job.c
  - kernel/tools/chrisbuild.c
  - kernel/tools/native_link.c
  - kernel/tools/shell.c
  - tools/kcc_main.c
  - tools/test_kcc.c
symbols:
  - kcc_compile_named
  - kcc_compile_source
  - kcc_last_error
  - kcc_last_asm
  - preprocess
  - parse_base
  - parse_struct_body
  - parse_expr
  - parse_binary
  - parse_stmt
  - parse_args
  - parse_initializer
  - parse_asm_stmt
  - emit_sync_cas
  - emit_sync_add
  - emit_sync_release
depends_on:
  - native-toolchain
  - semantic-analysis
  - native-codegen
  - calling-conventions
  - x86-instruction-encoding
related:
  - chrisasm
  - chriso
  - chrisld
  - self-hosting-bootstrap
---

# KCC architecture and C profile

## Scope

KCC is the native C-subset compiler used by the ChrisOS experimental native toolchain.

Its current compilation path is:

    C-like source
        -> KCC preprocessor
        -> direct recursive-descent parse + semantic/code-generation state
        -> textual x86-64 assembly
        -> ChrisAsm
        -> ChrisO object

KCC is not a GCC wrapper and does not lower through LLVM. It implements preprocessing, parsing, a compact type model, symbol handling, constant evaluation, stack-frame assignment and x86-64-oriented lowering inside `compiler/kcc/kcc.c`.

The compiler is intentionally narrower than ISO C. The important contract is therefore not “C supported / C unsupported” as a binary statement. KCC implements a concrete language profile whose accepted syntax and machine semantics are defined by the current source and tests.

![KCC compilation pipeline](../../assets/diagrams/kcc-en.svg)

## Public interface

`compiler/kcc/kcc.h` exposes four functions:

- `kcc_compile_named(file, src, out)`;
- `kcc_compile_source(src, out)`;
- `kcc_last_error()`;
- `kcc_last_asm()`.

`kcc_compile_named` preserves a source filename for diagnostics. `kcc_compile_source` is the filename-less entry point used by several in-kernel paths.

Successful compilation produces a `ChrisoImage`. The public API does not return assembly text as the primary artifact, but `kcc_last_asm` exposes the most recent generated assembly for testing and debugging.

The host command-line driver in `tools/kcc_main.c` reads a source file, invokes `kcc_compile_named`, serializes the resulting ChrisO image and writes the object file.

## Global compiler state

KCC keeps most compilation state in file-scope globals.

Major capacity limits include:

| Resource | Current limit |
| --- | ---: |
| generated assembly | 256 KiB |
| preprocessed source | 256 KiB |
| symbols | 2048 |
| macros | 256 |
| macro parameters | 4 |
| macro body | 768 bytes |
| structs | 80 |
| fields per struct | 32 |
| typedefs | 64 |
| enum constants | 512 |
| parameters/arguments | 16 |
| static initializer buffer | 4096 bytes |

Core state includes `g_p` for parser position, `g_file` and `g_line` for diagnostics, symbol/type tables, preprocessor tables, frame allocation state, temporary spill state and the generated assembly buffer.

`kcc_compile_named` resets these tables before each compilation.

This design is simple and allocation-light, but it also means one KCC process instance is **not reentrant**.

Two compilations executing concurrently against the same KCC globals can corrupt each other's parser, preprocessor, symbol and output state.

## Concurrency hazard in the in-kernel job path

This non-reentrancy is not only theoretical.

`kernel/metal/kcc_job.c` submits `kcc_worker` through the kernel job system, and APs execute `job_worker_forever`.

The worker calls `kcc_compile_source` directly without a KCC-specific lock.

In addition, `kcc_job_submit_path` stores the submitted path in a single static buffer:

    static char g_kcc_path[512];

and passes that shared buffer as the job argument.

Consequently, overlapping KCC job submissions have two independent race surfaces:

1. the submitted path can be overwritten before a worker consumes it;
2. multiple workers can enter KCC's process-global compiler state concurrently.

Until serialization or per-compilation state exists, the job interface should be treated as single-flight.

## Preprocessing model

KCC contains its own preprocessor instead of delegating to cpp.

It supports the mechanisms needed by the current kernel-oriented source profile:

- object-like macros;
- function-like macros;
- up to four macro parameters;
- nested macro expansion;
- token pasting with `##`;
- `#if`;
- `#ifdef` / `#ifndef`;
- `#elif` / `#else` / `#endif`;
- `defined(...)` in conditional expressions;
- quoted and angle-bracket includes;
- `#error`;
- ignored `#pragma` and `#warning` directives;
- inserted `#line` markers for source diagnostics.

Macro recursion is bounded. `pp_expand_into` stops recursive expansion after depth 8 by copying the remaining text rather than recursing indefinitely.

Include preprocessing rejects depth greater than 16.

Conditional nesting uses fixed 32-entry stacks.

## Built-in preprocessor environment

Every compilation starts with several predefined macros, including:

    __x86_64__ = 1
    __freestanding__ = 1
    __VERSION__ = "KCC"
    LIMINE_API_REVISION = 3

For selected standard headers such as `stdint.h` and `stddef.h`, KCC does not require a full hosted libc header implementation. The include path can synthesize integer-limit macros because the corresponding primitive types are built into the compiler.

For project headers, quoted includes first try a path relative to the including file. The fallback search list contains project directories such as:

- `third_party/limine`;
- `kernel/metal`;
- `kernel/gfx`;
- `kernel/wm`;
- `kernel/tools`;
- `kernel/fs`;
- `kernel/lang`;
- `kernel/net`;
- `compiler`;
- `compiler/chrisld`;
- `compiler/chrisasm`;
- `compiler/kcc`.

In freestanding builds, the source is read through the ChrisOS filesystem. Host builds use normal file I/O.

## Preprocessor limits and deviations

KCC is not a full C preprocessor.

Notable constraints include:

- no `#undef` implementation in the current directive dispatcher;
- only four function-like macro parameters;
- bounded logical lines;
- bounded macro body and expansion buffers;
- bounded include depth;
- no general standard include search environment;
- pragmas are accepted but ignored.

These rules are intentional implementation boundaries, not properties that should be generalized to standard C.

## Parser architecture

KCC uses direct recursive-descent parsing and emits assembly during parsing.

There is no independent AST or general-purpose intermediate representation for the KCC path.

Expression parsing is precedence driven. `parse_binary` handles 18 binary operator spellings and recursively parses the right-hand side at a higher precedence.

At precedence level zero, the same routine also handles:

- conditional `?:`;
- simple assignment;
- `+=`;
- `-=`;
- `|=`;
- `&=`;
- `^=`;
- `/=`.

Postfix parsing handles:

- function calls;
- indexing;
- postfix increment/decrement;
- `.` and `->` field access.

Unary parsing handles the supported unary operators, address/dereference forms, prefix increment/decrement, casts and `sizeof`.

## Value categories

`Val` carries the transient semantic state of an expression.

Relevant fields include:

- `Type type`;
- whether the value is an lvalue;
- whether it names a function;
- lvalue class;
- stack-frame offset;
- optional immediate value;
- global symbol name.

Lvalues are classified as:

    LV_NONE
    LV_LOCAL
    LV_GLOBAL
    LV_ADDR

This distinction drives address generation and stores.

`LV_ADDR` is used after operations such as pointer dereference, indexing or aggregate member selection when the compiler has computed an address and saved it in a temporary stack slot.

## Type representation

`Type` contains:

- kind;
- pointer flag;
- pointee size;
- array length;
- second-dimension length;
- struct ID;
- byte size;
- alignment;
- volatile qualifiers;
- function-pointer flag.

The recognized base categories are:

    void
    bool
    char
    int
    uint8_t
    uint16_t
    uint32_t
    uint64_t
    struct
    float

Pointers are always represented as eight-byte values.

Arrays carry size/stride metadata inside `Type`.

Function pointer declarators are recognized, but KCC does not preserve a full function signature type.

## Important C data-model deviation

KCC's data model is not LP64 C.

The current type table maps plain:

    int -> 8 bytes

while plain:

    unsigned -> 4 bytes

and `uint32_t` / `int32_t` both map to the same 4-byte unsigned-like internal kind.

Likewise `int64_t` and `uint64_t` share the same eight-byte internal kind.

Therefore source-level signedness is not represented with the fidelity expected from a conforming C implementation.

This is a current language-profile property and must be considered when deciding whether a production translation unit is KCC-safe.

## Signedness semantics are incomplete

The loss of signedness is visible in generated operations.

For division/modulo, `apply_bin` emits:

    xor rdx, rdx
    div rcx

which is unsigned x86-64 division.

Relational operators, however, use signed conditional branches such as `jl`, `jg`, `jle` and `jge`.

The same internal type categories can therefore participate in a mixture of signed and unsigned machine semantics.

KCC should not yet be described as preserving general ISO C integer conversion and signedness rules.

A future type system needs explicit signedness plus usual arithmetic conversions.

## Integer literals

`take_number` accepts decimal and hexadecimal integer constants.

It checks overflow against 64-bit unsigned range and accepts common `u/U/l/L` suffix characters, but those suffixes are consumed rather than mapped to a complete C integer-rank model.

Numeric primary expressions are emitted as 64-bit immediates.

This makes constant handling useful for kernel addresses, masks and flags while remaining intentionally simpler than standard C literal typing.

## Struct layout

`parse_struct_body` computes fields sequentially.

For ordinary structs:

    field_offset = align_up(current_offset, field_alignment)

The final struct size is rounded to the maximum field alignment.

For `__attribute__((packed))` structs, field alignment is forced to one.

KCC stores each field's concrete type and byte offset.

The implementation supports pointer fields, nested struct fields, function-pointer fields and arrays.

Struct arrays support up to two dimensions in the field parser.

There is no union parser in the current KCC source.

## Incomplete structs

A tagged struct can be introduced before its full body.

Such a placeholder starts with no fields and zero size.

Pointer declarations can refer to the incomplete type.

A direct non-pointer field of an incomplete struct is rejected.

This is enough to represent common forward-declared self-referential kernel structures.

## Initializers

Global initializer lowering uses a bounded 4096-byte staging buffer.

Supported forms include:

- scalar constant expressions;
- string arrays;
- array initializer lists;
- nested struct initializers;
- designated struct fields such as `.field = value`.

After parsing, KCC emits initialized bytes into `.data`.

Uninitialized globals go to `.bss` using `.zero`.

The initializer path is static: it evaluates constant expressions and materializes bytes before ChrisAsm builds the ChrisO sections.

## Constant-expression evaluator

KCC has a separate constant-expression evaluator, `ce_expr`.

It implements the same broad integer-operator families needed by enum values, array bounds, initializers and static assertions.

`_Static_assert` parses an integer constant expression and fails compilation when it evaluates to zero.

The evaluator is deliberately integer oriented.

It is not a general evaluator of arbitrary C expressions.

## `sizeof` and unevaluated expressions

`sizeof` can operate on a type or expression.

For expression-form `sizeof`, KCC parses the expression to discover its type, but snapshots and restores assembly-generation state:

- assembly length;
- overflow state;
- dead-store state;
- temporary count;
- frame allocation state.

The emitted side effects of the parsed expression are therefore discarded.

This is an important semantic detail: `sizeof(expr)` uses parser/type behavior without retaining normal runtime lowering.

## Float boundary

`float` exists as a recognized type so declarations and type parsing can represent it.

Native float execution is not implemented.

`reject_float` fails with:

    float is outside this subset

when a non-pointer float reaches ordinary load/store/arithmetic lowering.

This is preferable to silently emitting incorrect integer instructions, but it means graphics or math-heavy C using native floating point remains outside the KCC profile.

## Local storage and stack frame

Every emitted function starts with:

    push rbp
    mov rbp, rsp
    sub rsp, 2048

KCC therefore reserves a fixed two-KiB frame for every non-inline function regardless of actual local usage.

Normal local allocation uses `alloc_slot`.

Each object consumes at least eight bytes and is rounded to an eight-byte boundary.

The normal-local allocator stops when `g_frame + size > 1536`, leaving the lower part of the fixed frame for compiler temporaries.

## Temporary spill area

Expression temporaries use:

    -1600 - g_ntemp * 8

and `g_ntemp` resets at the start of each statement.

Unlike `alloc_slot`, `temp_slot` has no explicit lower-bound check.

Because the reserved frame ends at `rbp - 2048`, sufficiently complex single statements can allocate enough temporary slots to address below the fixed frame reservation.

The current source therefore contains a stack-frame capacity gap: ordinary locals are bounded, temporary spills are not.

A robust implementation should reject excess temporaries or dynamically size the frame.

## Calling convention

KCC follows a practical subset of the x86-64 System V integer calling convention.

The first six arguments use:

    rdi, rsi, rdx, rcx, r8, r9

Parameters are copied into frame slots when a function begins.

Arguments beyond six are read by the callee from positive offsets beginning at:

    [rbp + 16]

The caller reserves stack space for extra arguments and rounds that space to an even number of eight-byte slots so stack alignment remains compatible with the function prologue/call sequence.

Return values use `rax`.

The implementation is integer/pointer oriented; it does not implement the full ABI classification needed for floating-point, vector, large aggregate or mixed-class arguments.

## Function signatures are shallow

KCC tracks a function symbol and its return-like `Type`, but does not retain a complete parameter signature for ordinary function symbols.

Function-pointer declarators similarly set `is_func_ptr` while largely skipping the parameter declarator body.

Call lowering accepts up to 16 arguments but does not compare those argument types/count against a stored prototype.

An unknown identifier followed by `(` is also accepted as a function call target and defaults to a TY_INT-like result.

This is useful for compiling kernel code with external references, because ChrisAsm/ChrisO can leave the final call unresolved for the linker.

It also means KCC currently lacks standard C prototype checking and can accept ABI-incompatible calls.

## Inline functions

When a function definition is marked `inline`, KCC currently skips the braced function body rather than generating code or performing actual inlining.

This is a source-compatibility device, not an optimization implementation.

A program must not depend on KCC materializing that inline definition unless another resolvable definition/call path exists.

## Control flow

`parse_stmt` directly emits labels and branches for:

- blocks;
- `if` / `else`;
- `switch` / `case` / `default`;
- `while`;
- `for`;
- `break`;
- `continue`;
- `return`;
- `goto`;
- labels.

`switch` currently stores up to 64 case values and emits a linear compare/branch dispatch sequence.

Its dispatch complexity is therefore O(C) for C cases.

No jump-table selection or CFG optimization pass exists.

## Loop lowering

`while` uses a head label and end label.

`for` is implemented differently: the parser captures textual fragments for initializer, condition and step into bounded temporary strings, reparses them through `parse_from` and gives `continue` a target at the step label.

This explicit step target is covered by the host tests because a common lowering bug is to make `continue` jump to the condition while skipping the step.

## Labels and goto

Labels are emitted directly as assembly labels.

`goto name;` emits a direct assembly jump to that name.

There is no separate control-flow validation graph.

Final unknown labels are therefore expected to be rejected later by the assembler/linking boundary rather than by a high-level KCC CFG pass.

## Loads and stores

KCC loads most evaluated scalar results into `rax`.

Address calculations also use `rax`, with temporary values spilled into fixed frame slots as needed.

One-byte non-pointer objects use byte load/store instructions.

Volatile four-byte objects receive explicit dword accesses.

Other scalar accesses generally use eight-byte `mov` instructions.

This creates an important width limitation.

## 16/32-bit ordinary object-access gap

For a non-volatile global or address lvalue:

- size 1 receives a byte access;
- volatile size 4 receives a dword access;
- otherwise KCC currently uses an eight-byte access.

Consequently ordinary `uint16_t`, `int16_t`, `uint32_t` and `int32_t` object loads/stores can access eight bytes even when the declared object is two or four bytes.

For globals or adjacent aggregate fields, this can read or overwrite neighboring storage.

The current test suite verifies correct field offsets and specifically verifies volatile 32-bit accesses, but this source-level width rule remains a concrete correctness limitation that needs targeted regression tests and width-specific lowering.

## Volatile semantics

KCC preserves a volatile flag on types and pointees.

Volatile accesses clear the small dead-store optimization state and force the currently implemented memory access instead of allowing the previous store to be dropped.

The host suite checks volatile MMIO-style source and counts generated loads/stores.

This is meaningful evidence for the supported volatile cases, but it should not be generalized to every C volatile rule while width handling remains incomplete.

## Dead-store reduction

KCC includes a very small textual dead-store optimization for non-volatile globals.

After emitting a store, it records the symbol and assembly position.

If another eligible store to the same symbol occurs before an operation clears the state, `dead_store_drop` removes the previous store text from `g_asm`.

This is not SSA, data-flow analysis or alias analysis.

It is a local peephole mechanism constrained by explicit invalidation points.

Calls, loads and volatile activity clear the optimization state.

## Pointer operations

Pointer values are eight bytes.

`Type.pointee_size` provides scaling for:

- indexing;
- pointer increment/decrement.

Postfix indexing computes:

    address = base + index * element_size

and then represents the result as an `LV_ADDR` lvalue.

`.` uses the lvalue address of a struct.

`->` first loads the pointer and then adds the selected field offset.

Array expressions decay to pointers in `load_val` when an array lvalue is consumed as a value.

## Function pointers

KCC recognizes function-pointer declarations and indirect calls.

An indirect target is evaluated, spilled, arguments are prepared, then the target is restored and invoked with:

    call rax

Because full signature metadata is not preserved, indirect-call type checking is limited to the fact that the target has the function-pointer marker.

## Inline assembly profile

KCC accepts `asm` / `__asm__` syntax, but it is not a general GCC inline-assembly implementation.

The parser recognizes a bounded set of exact templates used by ChrisOS low-level code.

Examples include:

- `cli` / `sti` / `hlt` / `pause`;
- port `in` / `out` variants;
- reads/writes of CR2/CR3;
- stack-pointer read;
- `invlpg`;
- `lidt`;
- `str`;
- selected multi-instruction GDT reload sequence;
- AP stack switch;
- kernel-thread stack switch;
- user-mode `iretq` sequence.

Constraints are parsed only to the extent needed by these templates.

Unknown asm templates are rejected unless they match one of the explicit supported sequences.

This strategy intentionally turns the compiler's low-level compatibility surface into an allowlist rather than attempting to implement arbitrary GNU asm parsing.

## Atomic builtins

KCC special-cases:

- `__sync_bool_compare_and_swap`;
- `__sync_fetch_and_add`;
- `__sync_lock_release`;
- `__builtin_return_address(0)`.

CAS emits `lock cmpxchg` for 32- or 64-bit pointees.

Fetch-and-add emits `lock xadd`.

Lock release writes zero through the pointer.

Other names beginning with `__sync`, `__atomic` or `__builtin` are explicitly rejected as outside the subset.

This explicit failure behavior is important: unsupported compiler intrinsics do not silently degrade into unresolved external calls.

## Assembly as the KCC intermediate boundary

KCC does not produce machine bytes directly.

After parsing succeeds:

1. `g_asm` is null-terminated;
2. `chrisasm_assemble(g_asm, out)` runs;
3. ChrisAsm builds the final `ChrisoImage`.

If the assembly buffer overflows, KCC fails before invoking ChrisAsm.

If ChrisAsm rejects the generated text, KCC reports:

    assembler rejected the translation

The textual assembly boundary is useful because host tests can inspect `kcc_last_asm` and machine-byte tests can then inspect the assembled ChrisO sections.

## Diagnostics

`KccDiag` stores:

- file;
- line;
- column;
- severity;
- message.

Preprocessing inserts `#line` records so include-origin diagnostics can update `g_file` and `g_line` while the parser consumes the expanded source.

Most parser errors currently report column 1 rather than exact token column.

The diagnostic model is single-error oriented: `fail` marks `g_stuck` and compilation terminates rather than accumulating a rich recovery set.

## Memory ownership

The KCC front end itself uses fixed global arrays for most compiler state.

Include file contents are temporary heap allocations and are freed after recursive preprocessing.

The output `ChrisoImage` contains section allocations produced by ChrisAsm.

The caller owns the resulting object storage according to the ChrisO/native-toolchain lifetime rules.

This matters in the in-kernel build paths because section-complete object cleanup is not yet consistently implemented across all callers.

## In-kernel integration

KCC is reachable through several system paths:

- shell command compilation;
- `kcc_job_submit_path` asynchronous jobs;
- `chrisbuild_mk_kernel`;
- direct host tool use.

The shell `kcc` command compiles a source file to ChrisO and then sends it through `native_link_write_elf` to create a native ELF.

`chrisbuild_mk_kernel` compiles multiple C files, but the current builder still merges only TEXT contributions rather than preserving the full multi-object semantics documented in the native-toolchain chapter.

Therefore KCC's ability to produce rich ChrisO objects is ahead of the current in-kernel kernel-builder aggregation path.

## Validation evidence

`tools/test_kcc.c` exercises substantially more than toy expressions.

Current evidence includes:

- the level-0 fixture;
- undefined external call relocation;
- real `kernel/metal/serial.c`;
- real `kernel/metal/string.c`;
- `meminfo.c` and `pit.c`;
- normal versus packed struct offsets;
- volatile MMIO accesses;
- BSS and initialized DATA;
- designated aggregate initialization;
- enums;
- nested aggregates;
- arrays;
- function-pointer forms;
- `switch` and `goto`;
- `for` continue semantics;
- `sizeof`;
- `_Static_assert`;
- macro token pasting and conditional preprocessing;
- CR2/CR3 instructions;
- `invlpg`;
- `lidt`;
- atomics;
- `iretq`;
- port I/O;
- interrupt enable/disable;
- `hlt` and `pause`.

The test also contains a table of 26 real `kernel/metal/*.c` translation units and requires a selected symbol from each successful compilation.

That is direct evidence that KCC can process a non-trivial low-level kernel subset at this revision.

It is not evidence that every ChrisOS translation unit is accepted.

## What current tests do not establish

The current suite does not prove:

- ISO C conformance;
- correct signed/unsigned conversion semantics;
- correct two- and four-byte accesses for every non-volatile object;
- arbitrary inline assembly;
- native floating point;
- unions;
- complete variadic ABI;
- prototype/argument type checking;
- thread-safe parallel compilation;
- complete production-kernel rebuild;
- correctness of every extreme-capacity boundary.

Those claims require separate implementation and tests.

## Performance characteristics

KCC favors fixed arrays and linear searches.

`sym_find` searches symbols backward linearly.

Typedef, enum and struct lookup are also linear.

With the present limits, simplicity is useful for a teaching/research compiler.

For much larger source units, lookup cost can approach O(N) per identifier resolution and make total parse time more nearly quadratic in symbol-heavy inputs.

Assembly is also built through a single bounded text buffer, and several operations manipulate text directly.

This design prioritizes observability over optimizer-scale throughput.

## Security and robustness

KCC runs on source that may be read from the ChrisOS filesystem, so failure must remain contained to the compiler process/kernel context.

Positive properties include:

- bounded primary tables;
- bounded source/assembly/preprocessor buffers;
- include depth limit;
- conditional depth limit;
- integer-literal overflow checks;
- array-size checks;
- explicit rejection of unsupported builtins;
- explicit failure when ChrisAsm rejects generated text.

Important robustness gaps include:

- global mutable state exposed to concurrent in-kernel job execution;
- shared `g_kcc_path` job argument;
- unbounded temporary spill count relative to the fixed frame;
- object-width mis-lowering for ordinary 16/32-bit accesses;
- shallow function-signature checking;
- semantic signedness mismatches.

## Current limitations

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56:

- KCC implements a kernel-oriented C subset, not ISO C;
- plain `int` is eight bytes while plain `unsigned` is four bytes;
- fixed-width signed types are not represented with complete signedness;
- relational and division semantics do not implement a coherent C signedness model;
- native float operations are rejected;
- unions are not implemented;
- inline definitions are skipped rather than inlined or normally emitted;
- function prototypes/signatures are not fully retained for call checking;
- unknown identifiers followed by `(` can become unresolved function calls;
- ordinary non-volatile 16/32-bit memory accesses can be widened to eight bytes;
- every normal function reserves a fixed 2048-byte frame;
- temporary spills have no explicit bound against that frame;
- compiler state is global and non-reentrant;
- the asynchronous kernel job wrapper has additional shared-state races;
- preprocessor and inline assembly intentionally implement bounded subsets;
- production self-hosting remains incomplete.

## Roadmap boundary

A stronger KCC would benefit from:

1. per-compilation context instead of file-global mutable state;
2. a lock or single-flight contract until that refactor exists;
3. independent storage for every queued job path;
4. explicit signedness and integer-rank metadata;
5. usual arithmetic conversions;
6. width-correct 8/16/32/64-bit loads and stores;
7. full function signature types and call checking;
8. explicit variadic ABI support where required;
9. real inline semantics or a precise decision to emit inline bodies;
10. bounded/dynamically sized temporary stack allocation;
11. broader constant-expression correctness;
12. structured IR if optimization requirements outgrow direct assembly emission;
13. additional low-level asm templates only when source/tests require them;
14. full kernel translation-unit coverage;
15. end-to-end native-toolchain boot evidence.

These are roadmap items until source and tests demonstrate them.

## Source map and revision

`compiler/kcc/kcc.c` implements the preprocessor, parser, semantic state, constant evaluator, direct assembly lowering and KCC-to-ChrisAsm handoff.

`compiler/kcc/kcc.h` defines the public compile/diagnostic API.

`compiler/chrisasm/chrisasm.c` is the machine-code/object backend consumed by KCC.

`compiler/chrisld/chriso.h` defines the object image returned by KCC.

`tools/kcc_main.c` is the host CLI wrapper.

`tools/test_kcc.c` is the principal executable evidence for the supported C profile and low-level instruction paths.

`kernel/metal/kcc_job.c` exposes asynchronous in-kernel compilation and also demonstrates the current concurrency hazard.

`kernel/tools/chrisbuild.c` consumes KCC during the experimental kernel rebuild path.

`kernel/tools/shell.c` exposes interactive native compilation.

All current-behavior claims were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
