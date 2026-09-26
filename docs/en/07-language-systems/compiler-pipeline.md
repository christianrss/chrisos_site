---
id: compiler-pipeline
lang: en
type: technical-chapter
volume: 07-language-systems
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - cpu-datapath-isa
  - elf-linking
related:
  - chrisc-clvm
  - native-toolchain
---

# Compiler construction: source text to executable semantics

## Translation stages

A compiler transforms one formal language into another while preserving defined program meaning.

<figure class="figure">
<img src="../../assets/diagrams/compiler.svg" alt="Compiler stages">
<figcaption>A common decomposition. Individual compilers may combine or omit explicit stages.</figcaption>
</figure>

## Lexical analysis

The lexer converts characters into tokens: identifiers, keywords, literals, operators and punctuation. Source positions are retained so diagnostics can refer to line and column.

Lexing answers "what token is this text?" rather than "is this expression meaningful?"

## Parsing

The parser checks grammatical structure and produces a tree or equivalent representation. For example, precedence must distinguish `a + b * c` from `(a + b) * c`.

Recursive descent maps grammar structure directly to parser functions. Other strategies use generated LR/LL tables.

## Semantic analysis

A syntactically valid program can still be invalid:

- undefined symbol;
- incompatible types;
- wrong argument count;
- invalid lvalue;
- duplicate definition;
- illegal control-flow use.

Semantic analysis introduces symbol tables, scopes and type rules.

## Intermediate representation

An IR separates source-language syntax from final machine encoding. It can make optimization, verification and multiple backends easier.

IR is not mandatory for every small compiler, but lack of one can tightly couple parsing to one output language and make correctness harder to reason about.

## Code generation

Machine-code generation must obey the ISA and ABI: instruction encodings, register use, stack frames, calling convention, data layout and relocations.

Generating bytes that decode is insufficient. They must implement source semantics under every supported control-flow and type case.

## Object generation and linking

A compiler normally produces relocatable objects, leaving final inter-object addresses to a linker. This supports separate compilation and avoids requiring every source file at once.

## Diagnostics as part of the compiler

A compiler that silently ignores unsupported syntax is dangerous because successful exit no longer means the program was compiled.

Diagnostics therefore form a correctness interface: location, severity and explanation should distinguish rejected language from accepted semantics.

## Bootstrap compilers

Self-hosting introduces a lineage problem. A new compiler is initially built by an existing trusted compiler. Later stages compile newer copies of themselves.

Proof requires more than source language identity. The produced artifacts must be validated, and stage-to-stage convergence or differential behavior must be measured according to the project's self-hosting definition.

## ChrisOS has two language paths

ChrisOS contains a ChrisC → CLVM application path and a native kernel-oriented KCC/ChrisAsm/ChrisO/ChrisLd path. They solve different problems and should not be presented as one compiler with two names.

The following chapters separate these pipelines.
