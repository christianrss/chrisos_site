---
id: shader-frontend
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_pub.h
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_api.c
  - tools/test_shader.c
symbols:
  - sh_lex
  - sh_parse
  - sh_sem
  - sh_err
  - sh_compile
depends_on:
  - shaders-csir
  - compiler-pipeline
related:
  - csir
  - tgsi-backend
  - software-shader
---

# GLSL subset frontend

## Scope

This chapter isolates the language frontend of the ChrisOS shader compiler.

The frontend begins with source text and ends after semantic analysis has built a typed, slot-bound representation ready for CSIR lowering.

Its responsibility is therefore:

```text
source
  -> tokens
  -> AST
  -> scopes and symbols
  -> type/interface checks
  -> semantically valid shader program
```

The following chapter documents CSIR itself. This chapter focuses on what source programs the compiler accepts, rejects, and normalizes before that IR exists.

## A deliberate GLSL subset

The source syntax resembles GLSL, and `#version 330` is used by the in-tree examples, but the compiler does not claim GLSL 3.30 conformance.

The language is intentionally bounded to the features needed by ChrisOS.

Unsupported syntax should produce a diagnostic rather than silently acquiring host-compiler semantics.

Only vertex and fragment stages are accepted by `sh_compile`.

## Source and token limits

The frontend has fixed limits:

```text
source bytes     < 4096
tokens           <= 768
AST nodes        <= 512
symbols          <= 64
scope records    <= 48
parser nesting   <= 32
reported errors  <= 8
name length      < 40 in symbols
```

These are not tuning hints. They are hard capacities in the current structures.

The fixed limits make the compiler predictable inside the kernel and guest environment.

## Lexical state

Each token stores:

- kind;
- source offset;
- source length;
- line;
- column;
- integer value;
- float value.

The lexer therefore preserves enough source position to generate diagnostics without retaining a separate source map.

The source itself remains in the `ShComp` object.

## Preprocessor handling

Only a narrow `#version` form is accepted.

It must begin at the start of a logical source line.

A numeric version from 110 through 330 is accepted and stored.

Missing version numbers and versions outside that interval are errors.

Every other preprocessor directive is rejected as unsupported.

There is no macro expansion, conditional compilation, include processing or extension mechanism in the frontend.

## Comments and whitespace

Spaces, tabs, carriage returns and newlines are skipped while line/column state is updated.

Both:

```text
// line comments
/* block comments */
```

are recognized.

An unterminated block comment is an explicit lexical error.

Newlines also restore the "line start" state needed to recognize a later `#version` directive.

## Keywords

The current keyword set includes:

- interface/storage words: `in`, `out`, `uniform`, `const`;
- layout/interpolation words: `layout`, `smooth`;
- control flow: `if`, `else`, `for`, `return`, `discard`;
- scalar/vector/matrix types;
- `sampler2D`;
- boolean literals.

Identifiers outside this set remain ordinary identifiers.

## Explicitly unsupported qualifiers

The lexer has a separate list for words that resemble GLSL qualifiers but are not supported.

Examples include:

- `attribute`;
- `varying`;
- precision qualifiers;
- `inout`;
- `centroid`;
- `flat`;
- `noperspective`;
- `invariant`;
- `precise`;
- memory/storage qualifiers such as `readonly`, `coherent` and `shared`.

These become bad/unsupported qualifier diagnostics rather than ordinary identifiers.

This makes accidental use of unsupported GLSL features easier to detect.

## Operators

The parser recognizes the expected arithmetic and comparison subset:

```text
+ - * / %
== != < > <= >=
&& ||
!
++ --
=
```

Assignment is handled at statement level rather than as a general right-associative expression operator.

This distinction affects what forms can appear inside larger expressions.

## Expression precedence

Binary expressions are parsed with precedence climbing.

From lower to higher precedence:

1. logical OR;
2. logical AND;
3. equality;
4. relational comparison;
5. addition/subtraction;
6. multiply/divide/modulo.

Unary plus, minus, logical not and pre-increment/decrement bind above those binary groups.

Postfix syntax handles swizzles, indexing and post-increment/decrement.

## Swizzles

Swizzles may contain one through four components.

The accepted component families are:

```text
xyzw
rgba
```

A swizzle cannot mix the two naming families in one token.

For example, a combination such as `xg` is rejected.

The parser records the swizzle as a compact two-bit-per-lane mask.

Semantic analysis later verifies that every requested component exists in the source value.

Matrices cannot be swizzled.

## Indexing

The parser accepts bracket indexing syntactically.

Semantic analysis narrows it further: the index must be a compile-time constant integer and must be in range for the value.

Dynamic vector indexing is therefore not part of the current subset.

The index operation ultimately lowers to a lane selection rather than a general address computation.

## Constructors

Type names followed by parentheses are parsed as constructors.

Scalar, vector and matrix construction are supported only for the combinations implemented by semantic lowering.

Vector constructors require the supplied components to add up to the destination width, with some scalar broadcast/truncation forms.

Matrix constructors support:

- a constant scalar diagonal;
- one column value per matrix column.

Other matrix constructor patterns fail explicitly.

## Global declarations

A global declaration can begin with optional:

```text
layout(location = N)
smooth
in | out | uniform | const
```

followed by a type and name.

Only one primary qualifier from the in/out/uniform/const group is parsed in that position, with an additional `const` accepted after it.

The current frontend does not implement the full combinations allowed by desktop GLSL.

## layout syntax

Only:

```glsl
layout(location = N)
```

is accepted.

The token after `layout(` must literally be the identifier `location`.

The value must be an integer literal.

Other layout keys, comma-separated layout lists, binding qualifiers and format qualifiers are unsupported.

The location is stored on the AST declaration and later validated during slot binding.

## smooth qualifier

`smooth` is recognized and stored in the declaration qualifier flags.

In the inspected revision, there is no alternate interpolation mode to contrast with it: the frontend does not implement `flat` or `noperspective`, and downstream interpolation follows the normal varying path.

Thus `smooth` is accepted syntax, not a switch among several implemented interpolation policies.

## Functions

A function declaration consists of:

- return type;
- name;
- typed named parameters;
- mandatory body block.

There are no prototypes without bodies in this parser.

Parameter qualifiers are not implemented.

Semantic registration stores at most four parameter types.

A fifth parameter causes `too many parameters`.

## main

Semantic analysis searches registered functions for `main`.

A shader must contain:

```glsl
void main()
```

with zero parameters.

Missing main or any other main signature is rejected.

The compiler does not infer an entry point from source order.

## Blocks and statements

The statement parser supports:

- empty statements;
- blocks;
- declarations;
- expression statements;
- simple assignments;
- return;
- if/else;
- for;
- discard.

There are no `while`, `do`, `switch`, `break` or `continue` tokens in the implemented grammar.

For loops are parsed generically enough to form an AST, then semantic analysis applies much tighter restrictions for static unrolling.

## Assignments

Assignment is recognized after an expression has been parsed.

The AST can therefore syntactically contain an arbitrary expression on the left.

Semantic analysis deliberately narrows valid assignment targets to a simple identifier.

This means forms such as assigning directly to a swizzle or indexed lane are rejected with `assignment target must be a name`.

Inputs, uniforms, functions, samplers and `gl_FragCoord` are also non-assignable.

`gl_Position` is writable only with a vec4.

## Local declarations

Plain typed declarations are accepted inside blocks by reusing the declaration parser.

Interface qualifiers inside non-global scopes are rejected semantically with `qualifiers are only valid at global scope`.

Local variables can have initializers.

A local `const` becomes immutable after its initializer has been lowered.

## Global initializer caveat

The parser can syntactically attach an initializer to a global declaration.

However, global registration in the inspected semantic implementation records the symbol/interface but does not run general global initializer lowering.

The normal prologue initializes uniforms, stage inputs/outputs and built-ins, not arbitrary global local-style variables.

Code should therefore not rely on general initialized global variables or global const expressions in this revision unless separately tested.

This is a frontend/semantic gap worth closing explicitly.

## Scopes

Semantic analysis maintains a current scope ID and a fixed parent table.

A symbol records the scope in which it was defined.

Lookup walks the active scope chain.

Duplicate names are rejected when another symbol with the same name exists in the same scope.

Nested blocks create and destroy semantic scopes as they are lowered.

The scope table is limited to 48 records.

## Built-in symbols

Semantic analysis pre-registers:

```text
gl_Position : vec4
gl_FragCoord: vec4
```

before user globals.

Stage rules then restrict access:

- `gl_Position` is meaningful only in vertex shaders;
- `gl_FragCoord` is meaningful only in fragment shaders.

A vertex shader that never stores `gl_Position` is rejected.

## Symbol registration

Global AST nodes become symbols before the main body is lowered.

Declaration qualifiers determine whether a symbol is an input, output, uniform or ordinary symbol.

Functions receive body and parameter references.

This two-step registration allows user functions to be found even when called from code that is semantically processed later.

It also allows interface slots to be assigned before main execution is lowered.

## Attribute locations

Vertex inputs use up to eight attribute locations.

An explicit location is checked for:

- range below eight;
- uniqueness.

Inputs without explicit locations receive the next free slot.

The highest allocated location is recorded for later IR verification.

## Varying locations

Vertex outputs and fragment inputs share the varying-slot model.

Explicit locations must also fit below eight and be unique within the stage's slot allocation.

Unspecified varyings receive free slots automatically.

Program linking later matches fragment inputs to vertex outputs by name and type and creates the final remap.

Frontend slot allocation and cross-stage linking are therefore separate steps.

## Uniform allocation

Non-sampler uniforms receive constant slots.

A scalar/vector consumes one vec4 slot.

A mat3 consumes three.

A mat4 consumes four.

The aggregate high-water mark may not exceed 32 vec4 slots.

Sampler2D uses a separate slot counter limited to four.

A sampler declaration that is not a uniform is rejected.

## Fragment output rules

A fragment-stage `out` declaration must be vec4.

Only one fragment output is supported.

The frontend increments an output count during slot binding and rejects additional outputs.

This restriction is enforced before TGSI generation.

## Function-call semantics

User function calls are resolved through the symbol table.

Argument count must match.

Argument types must match except for the limited scalar compatibility rules implemented by the semantic layer.

Recursion is detected by checking the current function stack.

The call stack is limited to eight.

Functions are expanded semantically into the caller rather than emitted as runtime call instructions.

## Return restrictions

A non-void function used as a value must produce a return value.

The current statement lowering also requires a return to be the final statement of the function-level path being processed.

This is more restrictive than general GLSL control-flow return semantics.

It exists because functions are inlined into a simple bounded IR rather than compiled into independent control-flow graphs.

## If/else

If conditions must be scalar-like.

Semantic lowering emits explicit IF, optional ELSE and ENDIF IR markers.

There is no short-circuit control-flow lowering for logical AND/OR; the current semantic implementation lowers those operators arithmetically.

This distinction matters for expressions with side effects, although the current subset already has few side-effecting expression forms.

## for syntax versus semantics

The parser allows optional initializer, condition and step AST components.

Semantic analysis is much stricter.

The initializer must ultimately be an integer declaration with a compile-time-known initial value.

The condition must be reducible from the loop variable and compile-time integer values.

The step must be understood by the restricted step evaluator.

The loop variable cannot be modified in the body.

The compiler then unrolls at most eight iterations.

Thus parse acceptance does not imply runtime-loop support.

## discard

`discard;` parses as its own statement.

Semantic analysis accepts it only in fragment shaders.

Using it in a vertex shader produces an error.

There is no expression form of discard.

## Type compatibility

Assignments require matching types except for limited scalar-to-scalar compatibility.

Matrix/vector multiplication has dedicated rules.

Vector comparisons are rejected.

Division lowers through reciprocal and multiply.

Compile-time division by zero is diagnosed when the divisor is a known scalar zero.

Modulo is restricted to compile-time constant integers.

## Error recovery

The parser does not stop after the first syntax error.

`sync_stmt` skips tokens until a semicolon or an appropriate brace boundary is reached.

Parsing then attempts to continue until the error count reaches the fixed maximum.

This gives users several diagnostics from one compile while keeping recovery logic small.

Recovery is statement-oriented; it does not attempt full grammar repair.

## AST inspection

`sh_shader_ast` returns a textual dump created from the AST.

Each node line includes:

- node index;
- node kind;
- type when present;
- a short source token fragment.

This is useful for testing and compiler debugging.

It is a diagnostic representation, not a stable serialized AST format.

## Tests that exercise the frontend

`tools/test_shader.c` covers important frontend behavior.

It verifies:

- invalid swizzle rejection;
- diagnostic shader name and error text;
- unsupported preprocessor rejection;
- geometry-stage rejection;
- varying type mismatch;
- if/else parsing and semantics;
- a statically unrolled for loop;
- user-function parsing/calls;
- discard;
- malformed-source fuzz inputs;
- source/compiler lifecycle without leaks.

The test suite exercises actual compile paths rather than parsing isolated token fixtures.

## Current limitations

The grammar intentionally omits many GLSL constructs.

There is no macro preprocessor.

Only one layout key is supported.

Functions have at most four parameters and no prototypes.

Assignment targets are simple names only.

Dynamic indexing is unsupported.

General global initializers are not fully lowered.

Only one fragment output exists.

Interface locations are limited to eight.

The frontend, cache and registries are global structures without a complete concurrent compilation model.

These limits should be treated as the language definition of this revision, not as temporary undocumented behavior.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents the accepted GLSL-like grammar and semantic contracts before CSIR, with unsupported desktop-GLSL behavior called out explicitly.
