---
id: intermediate-representation
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm.h
  - compiler/il/il.h
  - compiler/il/il.c
  - compiler/cla/cla.h
  - compiler/cla/cla.c
  - compiler/lang_pipeline.c
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - tools/test_cla_gc.c
  - tools/test_chrisc_c17.c
  - tools/test_kcc.c
symbols:
  - NodeKind
  - Node
  - Compiler
  - gen_expr
  - gen_stmt
  - byte
  - push
  - branch
  - patch
  - ClvmOpcode
  - IlType
  - IlSig
  - il_verify
  - ClaMethod
  - ClaImage
  - cla_write
  - cla_load_bytes
  - Type
  - Val
  - kcc_compile_named
  - ChrisoImage
depends_on:
  - compiler-pipeline
  - parsing
  - semantic-analysis
related:
  - native-codegen
  - calling-conventions
  - chrisc-clvm
  - clvm-bytecode
  - jit
  - native-toolchain
  - kcc
---

# Intermediate representations

## Scope

An intermediate representation, or IR, is a program representation used between source-language parsing and final execution or target-machine code. The term covers a wide range of forms: abstract syntax trees, typed trees, control-flow graphs, three-address code, static single assignment form, stack bytecode, virtual-machine instructions, machine-oriented low-level IR and object-level relocation records.

ChrisOS does not currently have one universal compiler IR shared by all language systems.

Instead, the project contains several representation layers with different purposes:

- ChrisC builds an AST-like fixed table of Node records;
- ChrisC lowers those nodes directly to CLVM stack bytecode;
- compiler/il provides a small abstract type system and verifier over CLVM opcodes;
- CLA packages CLVM/IL bytes with method, type and reference metadata;
- KCC carries transient Type and Val state while parsing, then emits textual x86-64 assembly directly;
- ChrisAsm converts that assembly into ChrisO target object sections, symbols and relocations.

These layers should not be collapsed into one term. A syntax tree, bytecode stream, verification type lattice and native object file solve different problems.

![Intermediate representations in ChrisOS](../../assets/diagrams/intermediate-representation-en.svg)

## Why compilers introduce IR

A direct source-to-machine compiler can work, especially for a small language, but an IR creates a stable boundary between front end and back end.

A useful IR can provide:

- a simpler instruction vocabulary than the source language;
- explicit type and value semantics;
- normalized control flow;
- a place for optimization independent of parsing;
- a target for verification and debugging;
- portability across machine backends;
- stable source mapping;
- easier testing of transformations.

The cost is another representation to define, allocate, validate and keep semantically correct.

ChrisOS currently uses both approaches. ChrisC has a persistent AST-like representation before CLVM lowering. KCC deliberately fuses parsing, semantic actions and native assembly emission, avoiding a persistent general-purpose IR.

## Representation levels

It is useful to distinguish four conceptual levels.

A **high-level IR** preserves source concepts such as calls, fields, loops and typed expressions.

A **mid-level IR** usually normalizes source constructs into explicit operations and control-flow blocks while remaining target independent.

A **low-level IR** models machine-like operations, explicit loads/stores, branches and calling conventions.

A **virtual instruction set** is executable by an interpreter or JIT and may also act as a low-level IR.

In current ChrisOS, Node[] is closest to a high-level IR and CLVM bytecode is closest to a low-level stack IR / virtual ISA.

There is currently no general SSA, three-address or explicit control-flow-graph IR between them.

## ChrisC Node[] as an AST-like high-level IR

ChrisC parses source into a fixed:

    Node nodes[NODE_MAX]

table inside Compiler.

NodeKind distinguishes operations and statements such as:

- blocks and declarations;
- assignments;
- if, while, for, do and switch;
- return, break, continue and goto;
- integer, float and string literals;
- variables and indexing;
- direct and indirect calls;
- arithmetic, comparison and bitwise operators;
- address and dereference;
- casts and sizeof;
- ternary and comma expressions;
- field and pointer-field access;
- pre/post increment and decrement.

A Node stores integer references to left, right and third children, a next link, a value payload, source line and column, float classification, a structure/type side ID and a short name field.

This is more than a parse tree because nodes already contain semantic and lowering-oriented information. It is still AST-like because source constructs remain recognizable.

## Index-based graph representation

Children are represented by integer indexes rather than pointers.

This has several consequences.

First, the entire node graph lives in one bounded array. Allocation is an increment of nnode rather than a heap allocation per node.

Second, references remain stable while the table exists.

Third, serialization or inspection can conceptually use integer IDs without following arbitrary host pointers.

The trade-off is a hard NODE_MAX capacity and a representation tied to the lifetime of Compiler.

There is no garbage collection or node reclamation during compilation. Construction is effectively arena-like with a fixed arena.

## Information preserved by the ChrisC tree

The tree preserves enough information for later CLVM lowering to reconstruct source-level intent.

Source coordinates allow diagnostics and source mapping.

Node kind preserves operation semantics.

Child references preserve expression and statement hierarchy.

is_float allows lowering to choose floating CLVM operations or insert conversions.

sid and referenced symbol indexes preserve selected structure and storage semantics.

name carries identifiers or labels for operations that need textual identity.

Not every C type detail is canonicalized into the tree. As described in the semantic-analysis chapter, important facts remain in Symbol, StructDef, FuncDef and typedef tables.

The high-level representation is therefore a graph plus semantic side tables, not a self-contained typed AST.

## Control flow before lowering

At the Node level, control flow remains structured.

An if is still represented as an if node with condition and branch subtrees.

A loop remains a loop node rather than a basic-block cycle.

Logical operators and ternaries remain source-shaped nodes.

This makes generation straightforward but prevents many classic control-flow algorithms from operating directly.

There is no current pass that converts Node[] into:

    basic blocks
    predecessors/successors
    dominator tree
    dominance frontier
    phi nodes
    def-use chains

Consequently, ChrisC does not currently perform SSA-style optimization over its program representation.

## Direct lowering from Node[] to CLVM

gen_expr and gen_stmt recursively traverse the Node graph and emit CLVM bytes directly into Compiler.out.

The primitive emission helpers operate on the final byte stream.

byte writes one opcode byte.

push writes CL_OP_PUSH followed by a 32-bit little-endian immediate.

fpush writes CL_OP_FPUSH and the floating bit pattern.

branch reserves bytes for a relative branch.

patch later fills the relative displacement once the destination program counter is known.

The important architectural property is that there is no second instruction-list IR between the Node graph and CLVM bytes.

Once gen_expr or gen_stmt emits an opcode, that part of the program has already crossed into the virtual-machine instruction format.

## Branch fixups

Forward control-flow targets are not always known at first emission.

The branch helper emits a placeholder displacement and returns the byte offset of that instruction.

patch computes:

    displacement = target_pc - next_instruction_pc

and writes the relative value into the reserved bytes.

The current helper promotes the major branch/call forms to 32-bit variants such as CL_OP_JMP32, CL_OP_JZ32, CL_OP_JNZ32 and CL_OP_CALL32 when it creates those placeholders.

This is a classic fixup mechanism. It is not a CFG representation: control flow is encoded directly into instruction bytes and later patched.

## CLVM bytecode as a low-level stack IR

compiler/clvm/clvm.h defines the executable virtual instruction set.

The instruction set includes categories such as:

- constants: PUSH, PUSH64, FPUSH;
- integer arithmetic: ADD, SUB, MUL, DIV, MOD;
- floating arithmetic: FADD, FSUB, FMUL, FDIV;
- comparison operations;
- bitwise and shift operations;
- stack manipulation: DUP, DROP, SWAP;
- loads and stores with byte, 32-bit, 64-bit and float forms;
- relative control flow;
- direct and indirect calls;
- conversion operations FTOI and ITOF;
- argument/local instructions;
- object/field instructions;
- string and safepoint operations;
- system-call entry.

Because most arithmetic consumes operands from the VM stack and pushes results back, CLVM is a stack-machine representation rather than a register or three-address IR.

## Stack IR versus three-address IR

A stack expression such as:

    a + b * c

can conceptually lower to:

    load a
    load b
    load c
    mul
    add

A three-address IR might instead use explicit temporaries:

    t1 = mul b, c
    t2 = add a, t1

Stack IR is compact and maps naturally to an interpreter.

Three-address IR generally makes data dependencies more explicit and is usually easier for many optimization analyses.

ChrisC currently favors the compact executable stack form because CLVM is both compilation target and runtime ISA.

## CLVM is executable representation, not only compiler IR

Calling CLVM an IR is useful only with qualification.

The same byte stream is:

- produced by ChrisC;
- packaged into CLV images;
- interpreted by ClvmVm;
- consumed by the JIT;
- inspected by verification infrastructure.

Therefore CLVM is not merely a temporary internal compiler format. It is a stable execution boundary and virtual-machine ISA.

That makes changes to opcode semantics more consequential than changes to a private compiler-only IR.

## The compiler/il type layer

compiler/il does not define another instruction encoding.

It defines a small abstract type vocabulary:

    IL_VOID
    IL_I4
    IL_I8
    IL_F4
    IL_F8
    IL_PTR
    IL_REF

and an IlSig containing return type, argument count and up to eight argument type entries.

il_verify then walks CLVM bytecode while simulating an abstract operand stack.

The maximum verifier stack is currently 256 entries.

For PUSH it pushes IL_I4.

For PUSH64 it pushes IL_I8.

For FPUSH it pushes IL_F4.

Arithmetic pops operands and uses bin_t to derive a result category.

Loads replace an address-like stack entry with the loaded value category.

Stores consume address and value entries.

Conditional branches consume a condition.

This is an abstract interpretation over the bytecode, not a new emitted IR.

## Type merging in il_verify

bin_t implements a small widening rule.

If either operand is IL_F8, the result becomes IL_F8.

Otherwise IL_F4 dominates integer categories.

IL_I8 or IL_PTR produces IL_I8.

IL_REF has a special path.

Otherwise the result becomes IL_I4.

This is intentionally much smaller than the ChrisC or C type system.

The verifier tracks stack shape and broad categories, not complete source-language type identity.

## Current verifier guarantees

il_verify checks several important structural properties:

- instruction immediates do not run past the supplied method byte range for recognized instructions;
- stack pops do not underflow for many operations;
- abstract pushes do not exceed the 256-entry verification stack;
- selected field operations receive an address/reference-like category;
- CALLT can consume arguments according to a supplied signature;
- typed conversion opcodes update abstract stack type.

These checks can reject malformed byte streams before execution in paths that invoke the verifier.

## Current verifier limitations

The implementation is deliberately small and must not be described as a full bytecode proof system.

At the documented revision it does not construct a control-flow graph or propagate separate stack states along branches.

It does not merge abstract states at join points.

It does not verify that branch displacements target valid instruction boundaries.

The default opcode case currently advances without explicitly rejecting every unknown opcode.

RET may pop a value if one exists, but the implementation does not establish complete return-type conformance for all paths.

Its IlSig model supports args[8], while the current CLA wire format persists return type and argument count but does not serialize the full argument-type array.

Therefore il_verify is best understood as a bounded stack/type structural verifier, not a complete verifier comparable to a mature managed-runtime IL verifier.

## CLA as metadata around IL

CLA is a container, not a different instruction language.

ClaMethod stores:

- method name;
- relative byte offset;
- method byte size;
- IlSig metadata.

ClaType stores type name, size, GC bitmap and field count in memory.

ClaImage groups methods, types, referenced assembly names and one IL byte region.

cla_write serializes that metadata followed by the IL bytes.

cla_parse reconstructs the view.

cla_load_bytes validates each method range and calls il_verify on each method slice before accepting the image. It also resolves named CLA references against already loaded assemblies.

Thus CLA adds module/method/type metadata around executable IL without transforming the instruction stream into a new IR.

## Companion CLA generation in the language pipeline

The current language pipeline demonstrates this distinction clearly.

After ChrisC has produced code_buffer and the CLV image is written, the pipeline also constructs a small ClaImage.

It creates one method named main, points it at the same code buffer, records the method size and an IL_I4 return classification, then writes a companion CLA file.

The code bytes are reused. There is no separate ChrisC-to-CLA lowering pass.

CLA is therefore a metadata/package layer over the already generated CLVM instruction stream in this path.

## KCC deliberately has no persistent general IR

KCC follows another architecture.

During expression parsing it carries a Val containing Type information, lvalue classification, frame/global/address location and immediate state.

Those records are transient semantic/code-generation state.

The parser emits textual x86-64 assembly into g_asm while it recognizes the source program.

At the end of kcc_compile_named:

    preprocess
        ->
    compile_unit
        ->
    assembly text in g_asm
        ->
    chrisasm_assemble
        ->
    ChrisoImage

There is no persistent AST and no target-independent instruction graph between parsing and assembly.

## Is KCC assembly an IR?

Textual assembly can be called an intermediate representation in the broad pipeline sense because it exists between KCC source parsing and ChrisO machine objects.

However, it is target-specific x86-64 assembly, not a portable compiler IR.

Registers, instructions, addressing and calling behavior are already machine-oriented.

That means a future non-x86 backend could not simply reuse the current g_asm stream.

A target-independent IR would have to sit earlier in the pipeline.

## ChrisO is an object representation, not a compiler IR

ChrisAsm writes a ChrisoImage.

ChrisoImage contains target sections:

- text;
- rodata;
- data;
- bss;

plus ChrisoSym entries and ChrisoRel relocation records.

This representation is already machine-code/object territory.

It supports linking, symbol resolution and relocation, but it does not preserve arithmetic expression semantics, source loops or typed operations suitable for target-independent optimization.

For documentation purposes, ChrisO belongs after native code generation rather than in the main IR layer.

## Optimization consequences of current architecture

The current ChrisC design permits tree-local transformations before emission, but there is no general optimization pass framework over Node[].

Once CLVM bytes are emitted, high-level relationships are harder to recover.

The current KCC design can perform local optimizations during emission, such as its dead-store handling, but it does not have a stable program graph for global analyses.

Missing general IR infrastructure means there is currently no project-wide framework for:

- constant propagation over CFGs;
- common subexpression elimination;
- dead-code elimination based on liveness;
- loop-invariant code motion;
- register-independent instruction scheduling;
- SSA-based value numbering;
- generic target lowering.

This does not mean no optimization exists. It means optimization is implemented locally rather than through a shared IR pass pipeline.

## Complexity and memory behavior

Node allocation is O(1) per node until NODE_MAX is reached.

A full recursive traversal by gen_expr/gen_stmt is generally O(n) in the number of visited nodes.

Byte emission is append-oriented and O(1) per emitted byte/instruction aside from fixup bookkeeping.

il_verify is a linear bytecode walk for the instruction sequence it scans, with a fixed 256-entry abstract stack.

KCC avoids an AST allocation cost but pays by coupling parse-time state to backend emission and by making rollback necessary for contexts such as sizeof expressions.

These are different engineering trade-offs rather than one universally superior design.

## Validation evidence

ChrisC language tests exercise source constructs that create Node trees and then execute the resulting CLVM.

test_chrisc_c17.c covers a broad subset including structures, casts, arrays, function pointers and control flow.

tools/test_cla_gc.c constructs a CLA image, writes it, reloads it, verifies an IL method and exercises reference loading.

KCC tests compile focused snippets and real kernel sources through assembly into ChrisoImage.

The build system also compiles compiler/il, CLA and the runtime language pipeline into the project.

These tests establish that the described representation paths are active. They do not establish properties such as SSA correctness because SSA does not currently exist in this compiler pipeline.

## Current limitations

At the documented revision:

- there is no universal ChrisOS compiler IR;
- ChrisC Node[] is AST-like and not a normalized CFG IR;
- type information is partly stored in semantic side tables rather than fully attached to every node;
- ChrisC lowers directly from Node[] to CLVM bytes;
- there is no general three-address or SSA representation;
- there are no explicit phi nodes, dominator structures or def-use chains;
- CLVM is executable VM bytecode, not merely a private compiler IR;
- compiler/il verifies CLVM using a small abstract type system rather than defining a separate instruction set;
- il_verify does not perform full control-flow verification;
- CLA is primarily a metadata/container format around IL;
- KCC emits target-specific assembly during parsing and has no persistent general AST/IR;
- ChrisO is native object representation after code generation;
- optimization is local and subsystem-specific rather than organized around a shared pass manager.

## Roadmap boundary

A future compiler architecture could introduce a typed target-independent IR between semantic analysis and both CLVM/native backends.

A useful design might include:

- explicit basic blocks;
- typed virtual registers or SSA values;
- load/store and address operations with clear widths;
- normalized calls and returns;
- explicit conversion operations;
- source spans;
- function signatures;
- target-independent control flow;
- verifier invariants;
- deterministic serialization for debugging;
- pass interfaces for analysis and transformation.

ChrisC could lower Node[] into that IR.

KCC could parse into the same or a compatible native-oriented form.

CLVM and x86-64 would then become separate backends from a shared semantic representation.

Such an architecture could enable cross-backend differential tests and reusable optimization passes.

None of this is current behavior until corresponding source and validation exist.

## Source map and revision

The ChrisC high-level representation and lowering are in compiler/chrisc/chrisc.c, especially NodeKind, Node, Compiler.nodes, gen_expr, gen_stmt, byte, push, branch and patch.

The executable low-level representation is defined by ClvmOpcode in compiler/clvm/clvm.h.

The abstract verifier type layer is in compiler/il/il.h and compiler/il/il.c.

CLA metadata and loading are in compiler/cla/cla.h and compiler/cla/cla.c, with companion CLA generation visible in compiler/lang_pipeline.c.

KCC's direct source-to-assembly path is in compiler/kcc/kcc.c, ending in chrisasm_assemble and ChrisoImage.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
