---
id: csir
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/gfx/shader/sh_exec.c
  - kernel/gfx/shader/sh_tgsi.c
  - kernel/gfx/shader/sh_api.c
  - tools/test_shader.c
  - tools/test_gfx3d_abi.c
symbols:
  - sh_sem
  - sh_opt
  - sh_verify
  - sh_dump_ir_buf
  - sh_exec_ir
  - sh_shader_save_csi
  - sh_shader_load_csi
depends_on:
  - shader-frontend
related:
  - shaders-csir
  - tgsi-backend
  - software-shader
---

# Chris Shader IR

## Scope

Chris Shader IR, or CSIR, is the compact intermediate representation shared by the ChrisOS shader compiler's two execution paths.

After the GLSL-like frontend has resolved scopes, types, interface slots, constructors, built-ins and bounded control flow, semantic lowering emits CSIR.

The same instruction stream is then consumed by:

- the TGSI text emitter used by VirGL;
- the software interpreter used by CPU shader execution.

That makes CSIR the semantic boundary of the shader subsystem.

A useful model is:

```text
typed shader semantics
        |
        v
      CSIR
      /  \
     /    \
    v      v
  TGSI   interpreter
 VirGL      CPU
```

The IR is intentionally small, linear and bounded. It is not SSA and it is not a general compiler IR.

## Fixed capacities

The current compiler allocates CSIR storage inside `ShComp`.

The relevant capacities are:

```text
SH_IR_MAX   = 384 instructions
SH_IMM_MAX  = 160 float immediates
SH_TEMP_MAX = 96 temporaries
```

There is no dynamic growth beyond these limits.

If semantic lowering would exceed a pool, compilation emits an error and stops producing a valid shader.

This keeps memory requirements deterministic in the kernel environment.

## Instruction record

Each instruction is represented by:

```c
typedef struct Ir {
    uint8_t op;
    uint8_t ty;
    uint8_t ncomp;
    uint8_t pad;
    int16_t dst;
    int16_t a, b, c;
    int16_t aux;
    int16_t aux2;
} Ir;
```

With the current field layout, one record occupies 16 bytes.

The complete 384-entry instruction array therefore occupies 6144 bytes inside `ShComp`.

The record is deliberately generic: `aux` and `aux2` change meaning by opcode.

## Not SSA

CSIR temporaries are integer indices into a fixed temporary file.

They do not have SSA versioning, phi nodes or basic-block ownership.

An instruction can write an already allocated destination temporary.

`IR_SETLANE`, for example, mutates one lane of an existing destination vector.

This is one reason the optimizer is intentionally conservative: common SSA assumptions do not apply.

## Temporary model

The software interpreter materializes temporaries as:

```text
float tmp[96][4]
```

Each ordinary temporary therefore behaves like a four-lane float register.

Scalars use lane zero.

Vectors use one to four lanes.

Matrices use consecutive temporaries, one column per temporary.

A mat3 consumes three consecutive temporaries; a mat4 consumes four.

The type field describes semantic type, but the physical interpreter storage is float-based.

## Integer and boolean representation

Integers and booleans are represented through the same float temporary storage in the software executor.

Integer truncation uses `IR_TRUNC`.

Comparisons produce 1.0 for true and 0.0 for false.

Control flow tests lane zero against zero.

The IR is therefore typed semantically but not backed by separate integer and floating-point register files.

## Immediate pool

Literal constants are stored separately in:

```text
float imm[160]
```

An `IR_CONST` instruction uses `aux` as the starting immediate index and `ncomp` as the number of values.

The instruction writes those values into the destination temporary and zeroes unused lanes in the software interpreter.

Keeping immediates out of the 16-byte instruction record makes the instruction format fixed-size.

## Constant lowering

Semantic analysis performs some compile-time evaluation before IR emission.

Known scalar and vector arithmetic can produce a new immediate-backed temporary instead of runtime arithmetic.

Loop bounds are evaluated statically.

Several constructor paths also materialize constant vectors or matrix columns.

CSIR therefore receives a partially folded program rather than a literal translation of the AST.

## Core data movement

The basic movement instructions are:

```text
IR_CONST
IR_MOV
IR_SWZ
IR_SETLANE
```

`IR_MOV` copies the requested component count.

`IR_SWZ` uses two bits per requested lane in `aux` to select source components.

`IR_SETLANE` writes one destination lane from one source lane; `aux` selects the destination lane and `aux2` the source lane.

These instructions support constructors, assignments and vector decomposition without a richer aggregate-value representation.

## Arithmetic instructions

The primary arithmetic family contains:

```text
IR_ADD
IR_SUB
IR_MUL
IR_MAX
IR_MIN
IR_ABS
IR_DOT
IR_RSQ
IR_RCP
IR_SIN
IR_COS
IR_POW
IR_TRUNC
IR_CMP
```

Most component-wise operations use `ncomp`.

`IR_DOT` uses `aux` as the vector width.

`IR_CMP` uses comparison codes:

```text
CMP_LT
CMP_GT
CMP_LE
CMP_GE
CMP_EQ
CMP_NE
```

The software executor returns scalar boolean values as 0.0 or 1.0.

## Reciprocal-based division

The frontend does not need a separate divide opcode.

Division lowers into reciprocal plus multiply.

This keeps the IR smaller and maps naturally to backends that already expose reciprocal operations.

In the software interpreter, reciprocal of zero yields zero rather than infinity.

Compile-time scalar division by a known zero is rejected earlier by semantic analysis.

Backend equivalence around exceptional floating-point cases should therefore be tested deliberately.

## Built-ins as IR compositions

Several GLSL-like built-ins do not have dedicated CSIR opcodes.

For example:

- `normalize` lowers to dot, reciprocal square root and multiply;
- `length` lowers through dot, RSQ and reciprocal;
- `clamp` lowers to max followed by min;
- `mix` lowers to arithmetic;
- `reflect` lowers to dot and vector arithmetic;
- `cross` is assembled from scalar swizzles, multiplies and subtracts.

The IR instruction set is smaller than the source-language built-in set.

## Matrix operations

Two dedicated matrix instructions exist:

```text
IR_MULMV
IR_MULMM
```

Matrices are column-major in shader semantics.

For matrix-vector multiplication, `aux` carries the number of columns, normally three or four.

Matrix-matrix multiplication writes consecutive destination temporaries, one output column per temporary.

The verifier explicitly accepts only 3×3 and 4×4 matrix widths for `IR_MULMM`.

## Sampling

`IR_SAMPLE` represents a 2D texture sample.

`aux` is the sampler slot.

The coordinate comes from source temporary `a`.

The destination is a four-component sampled color.

The IR deliberately does not encode a full texture object, filtering mode or address mode; those are backend/runtime concerns.

The software interpreter currently receives one CPU texture pointer and uses its own nearest/clamp sampling semantics.

The TGSI backend maps the sampler slot into shader declarations and texture instructions.

## Interface loads

The input-side instructions are:

```text
IR_LOAD_ATTR
IR_LOAD_VAR
IR_LOAD_UNI
IR_LOAD_FCOORD
```

`IR_LOAD_ATTR` uses `aux` as vertex attribute location.

`IR_LOAD_VAR` uses `aux` as varying slot.

`IR_LOAD_UNI` uses `aux` as the base vec4 constant slot and `aux2` as the number of consecutive vec4 slots.

This allows mat3 and mat4 uniforms to load into consecutive temporaries.

`IR_LOAD_FCOORD` has no external slot and loads the fragment coordinate supplied by the executor/backend.

## Interface stores

Stage outputs use:

```text
IR_STORE_POS
IR_STORE_VAR
IR_STORE_COLOR
```

`IR_STORE_POS` is valid only in the vertex stage.

`IR_STORE_VAR` writes a varying slot in `aux`.

`IR_STORE_COLOR` is valid only in the fragment stage.

The current shader language has one fragment color output, so there is no render-target index in `IR_STORE_COLOR`.

## Varying remap

A compiled fragment shader initially refers to its own varying slots.

Program linking matches fragment inputs to vertex outputs by name and type.

Both the TGSI emitter and software executor can receive a `var_remap` table.

For `IR_LOAD_VAR`, a mapped slot replaces the original fragment-local slot.

This allows shader compilation to remain stage-local while linking establishes the final cross-stage interface.

## Linear control flow

CSIR has only three structured control-flow markers:

```text
IR_IF
IR_ELSE
IR_ENDIF
```

There are no branch targets, labels, jumps, loops, phi nodes or function-call instructions.

The source-language `for` construct is statically unrolled before IR completion.

User functions are semantically inlined.

This leaves the final IR as a single linear instruction list with nested structured conditionals.

## IF semantics

`IR_IF` reads source temporary `a`, lane zero.

Zero is false; any nonzero value is true.

The software interpreter keeps two fixed 32-entry stacks: one for skip state and one for branch state.

Nested false branches remain skipped until their matching ELSE/ENDIF.

The verifier separately checks IF/ELSE/ENDIF balance before execution.

## ELSE and ENDIF invariants

The verifier rejects:

- ELSE without an open IF;
- more than one ELSE for the same IF;
- ENDIF without an IF;
- nesting deeper than 32;
- nonzero control-flow depth after the final instruction.

The interpreter also contains runtime defensive checks.

Thus malformed control flow is rejected both structurally and, if somehow reached, defensively during software execution.

## Discard

`IR_DISCARD` is valid only in fragment shaders.

In the software interpreter it sets the discarded flag when one is supplied and returns immediately from shader execution.

TGSI maps the operation to the backend discard/kill behavior.

There is no vertex-stage discard.

## Instruction emission

Semantic lowering appends records through a small `emit` helper.

If `nir` reaches 384, the compiler reports:

```text
shader exceeds the instruction limit
```

Temporary allocation similarly reports a limit error above 96, and immediate allocation fails above 160 floats.

These bounds are checked at construction time before later verification.

## Semantic prologue

Before lowering `main`, the compiler emits a prologue from the registered interface.

It allocates temporaries and emits:

- uniform loads;
- vertex attribute loads;
- fragment varying loads;
- fragment-coordinate load;
- zero initialization for stage outputs and `gl_Position`.

The main body then operates on those temporaries.

This is why the IR already contains explicit interface traffic rather than symbolic variable names.

## Symbol names disappear

Most source-level symbol identity is gone from CSIR instructions.

Uniforms, attributes, varyings and samplers are represented by numeric slots.

Locals are represented by temporaries.

Functions are inlined.

The compiler still keeps the symbol table in `ShComp` for dumps, linking and metadata, but the instruction stream itself does not depend on local variable names.

## Optimization

`sh_opt` performs four passes.

Each pass counts temporary uses in instruction operands.

For a selected set of pure instructions, a destination with zero uses causes the instruction opcode to be changed to `IR_NOP`.

The removable set includes constants, moves, swizzles, basic arithmetic, min/max, abs, dot, reciprocal operations, trig, pow, truncation, compare and matrix-vector multiply.

It deliberately excludes operations whose semantics are less obviously removable in the current implementation.

## Optimizer limitations

This pass is not full dead-code elimination.

It does not remove entire unreachable branches.

It does not compact the instruction array after converting instructions to NOP.

It has no constant propagation dataflow pass, common-subexpression elimination, register allocation, SSA conversion or liveness interval analysis.

Four iterations are used so eliminating one dead result can expose another producer as dead.

## Why SETLANE is special in use counting

`IR_SETLANE` mutates its destination rather than defining a wholly new value.

The optimizer therefore treats the destination as a use as well as a write when counting references.

Without that rule, a prior value in untouched lanes could be incorrectly considered dead.

This is an example of the non-SSA nature directly affecting optimization logic.

## Verification stage

After optimization, `sh_verify` validates the IR before TGSI emission or normal shader acceptance.

It first checks stage, temporary count and instruction count.

Then it scans every non-NOP instruction.

Verification is structural and range-oriented; it is not a proof of full program semantics.

## Temporary validation

A valid temporary index must be:

```text
0 <= t < ntmp
t < SH_TEMP_MAX
```

Ordinary destinations and operands are checked against that predicate.

Multi-temporary operations such as uniform loads and matrix multiplication additionally verify the final consecutive temporary.

This prevents an IR record from addressing beyond the allocated temporary file.

## Stage restrictions

The verifier enforces:

- `IR_STORE_POS` only in vertex shaders;
- `IR_STORE_COLOR` only in fragment shaders;
- `IR_DISCARD` only in fragment shaders.

This protects both loaded CSI blobs and in-memory compiler output from stage-inappropriate instructions.

## Slot restrictions

The verifier checks sampler, attribute and varying ranges.

`IR_SAMPLE` must reference a sampler slot from zero through `samp_hi`.

`IR_LOAD_ATTR` must not exceed `attr_hi`.

Varying load/store slots must remain in 0..7.

`IR_LOAD_UNI` verifies a nonnegative base slot indirectly through its own fields and validates destination span; the compiler's semantic path is responsible for the normal 32-slot uniform allocation.

## Constant validation

For `IR_CONST`, the verifier checks that:

- destination temporary is valid;
- immediate index is nonnegative;
- `aux + ncomp` does not exceed `nimm`.

This protects the immediate pool from out-of-range reads.

It does not validate floating-point contents themselves.

NaNs or unusual finite values are data, not structural corruption.

## Matrix validation

`IR_MULMM` accepts only an `aux` width of three or four.

It verifies destination span and initial source temporaries.

The compiler's normal lowering allocates contiguous matrix columns.

The verifier is primarily guarding range/shape assumptions rather than reconstructing complete matrix type provenance.

## IR dump

`sh_dump_ir_buf` creates a human-readable representation.

The output begins with shader name and stage, then lists interface symbols such as uniforms, inputs and outputs.

After:

```text
block 0:
```

it prints each non-NOP instruction with destination, mnemonic, selected operands and selected aux data.

The "block 0" label does not imply a general basic-block graph. The IR remains one linear structured list.

## Public IR inspection

`sh_shader_ir` exposes the dump stored in the compiled shader.

Tests use this to confirm that semantic lowering produced expected stores and other recognizable operations.

The textual dump is a debugging surface, not a stable machine-readable interchange format.

The binary CSI form is the separate persistence mechanism.

## Software execution

`sh_exec_ir` executes CSIR directly.

It zeroes the temporary file and initializes result outputs.

It then walks instructions from zero to `nir - 1`.

Control-flow markers update the skip stack; skipped ordinary instructions are ignored.

Arithmetic and interface operations manipulate the temporary array.

The interpreter is useful both as a backend and as an executable reference for CSIR semantics.

## Execution versus verification

The interpreter contains some defensive checks, but callers are expected to execute verified compiler output.

For example, several handlers test destination/source indices before operating, while others rely more directly on invariants already established by `sh_verify`.

The architectural contract is therefore:

```text
construct/load
  -> optimize when compiled from source
  -> verify
  -> backend execution/emission
```

Verification is not intended to be skipped for untrusted serialized input.

## TGSI consumption

The TGSI emitter walks the same linear CSIR and converts operations into textual TGSI instructions/declarations.

It uses interface high-water marks and optional varying remap metadata.

Some CSIR operations expand into multiple TGSI instructions.

Therefore instruction count in CSIR is not expected to equal instruction count in TGSI text.

The next chapter documents that backend mapping in detail.

## CSI binary format

CSIR can be serialized with `sh_shader_save_csi`.

The blob layout is:

```text
32-byte header
N * sizeof(Ir) bytes
M * sizeof(float) immediate bytes
```

The header contains eight 32-bit words:

```text
0 magic      0x52495343
1 version    1
2 stage
3 nir
4 nimm
5 ntmp
6 checksum
7 reserved
```

The magic corresponds to the bytes "CSIR" in little-endian storage.

## Raw-structure portability

The serialized instruction body is a direct byte copy of the in-memory `Ir` array.

Unlike the VirtIO protocol encoders, CSI does not serialize each field explicitly into a canonical endian/packing representation.

The current format therefore assumes the same `Ir` layout and compatible endianness/ABI between writer and reader.

It should be treated as a ChrisOS-internal experimental format rather than a portable cross-architecture IR standard.

## CSI checksum

The checksum is a simple additive byte sum over the serialized IR records.

It does not cover the immediate pool.

A modified immediate can therefore leave the checksum unchanged.

The loader still validates blob length and structural IR invariants, but literal-value integrity is not authenticated.

A future format should checksum or hash the complete payload and version the exact wire layout.

## CSI loading

The loader validates:

- minimum 32-byte header;
- magic and version;
- stage is vertex or fragment;
- instruction/immediate/temp counts within fixed limits;
- total blob length exactly matches the derived size;
- IR checksum;
- `sh_verify`.

It then attempts to emit TGSI.

If TGSI emission fails, a shader object can still be returned with `ok = 0`.

## CSI metadata gap

CSI stores only:

- stage;
- IR;
- immediate pool;
- temporary count.

It does not store:

- symbols;
- uniform names/slot high-water metadata;
- attribute high-water metadata;
- sampler high-water metadata;
- varying interface declarations;
- original source.

Because a newly allocated `ShComp` is zeroed during load, omitted metadata remains at zero rather than being reconstructed from the IR.

This makes general CSI round-tripping incomplete.

## Consequence for verification

The metadata gap is observable.

For example, a loaded shader that uses an attribute slot above zero can fail `IR_LOAD_ATTR` verification because `attr_hi` was not restored.

A sampler slot above zero can fail because `samp_hi` was not reconstructed.

The current unit test serializes a constant vertex shader without rich interface requirements, so it does not exercise this limitation.

CSI should not yet be treated as a general production shader cache.

## Test evidence

`tools/test_shader.c` verifies that compiled shaders expose IR text and that CSIR executes correctly through the software backend.

The suite exercises matrix transforms, texture sampling, lighting, conditionals, unrolled loops, functions, discard and trigonometric operations.

It also serializes a simple shader, reloads it, flips one byte in the IR region and requires the corrupt blob to be rejected.

The test does not cover arbitrary CSI interface metadata.

## Cross-backend evidence

The same semantic IR feeds both software execution and TGSI.

`tools/test_gfx3d_abi.c` compares CPU-side matrix expectations with shader execution for identity, translation, rotations, scale, view and projection cases.

This helps verify that the central representation preserves the intended matrix conventions before backend-specific command generation.

It does not prove every transcendental operation is bit-identical across CPU and VirGL.

## Complexity

IR verification and dumping are linear in instruction count.

The optimizer performs four scans for use counting plus four scans for elimination, so its cost remains O(IR) with a small fixed multiplier.

Software execution is O(IR) per shader invocation before considering texture access or rasterization frequency.

With at most 384 instructions, the design favors bounded predictable behavior over large-shader throughput.

## Security and robustness boundary

CSIR is still trusted kernel data during normal compilation, but CSI loading creates a binary-input boundary.

Fixed instruction/temp/immediate limits, exact length checks and structural verification reduce the damage malformed blobs can cause.

The remaining portability, metadata and checksum gaps mean CSI should not be accepted as a hardened untrusted interchange format without further work.

## Current limitations

CSIR is linear, non-SSA and single-function after lowering.

There are no runtime loops, general calls, labels, jumps or phi nodes.

The register file is float-based even for integer/bool semantics.

Optimization is minimal.

The serialized form is ABI-dependent and incomplete for interfaces.

The IR is intentionally sufficient for the current shader subset rather than designed as a universal compiler IR.

## Recommended next tests

Useful additions include direct verifier tests for every invalid opcode family, unbalanced control flow, bad sampler/attribute slots, invalid matrix spans and immediate overflow.

CSI tests should include shaders using attribute location 3, multiple uniforms, sampler slot 1 and varyings, then prove either correct metadata reconstruction or explicit rejection.

A full-payload checksum test should mutate immediate bytes and require detection after the format is hardened.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents CSIR as the bounded semantic interface shared by the software interpreter and TGSI backend, including optimizer, verifier and CSI persistence limits.
