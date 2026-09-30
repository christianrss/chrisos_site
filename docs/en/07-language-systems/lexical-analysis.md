---
id: lexical-analysis
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisc/chrisc.c
  - compiler/chrisc/chrisc.h
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - compiler/clvm/clasm.c
  - tools/test_chrisc_c17.c
  - tools/test_chrisc_read_diag.c
  - tools/test_fuzz_chrisc.c
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_clasm.c
symbols:
  - TokenKind
  - Token
  - keyword
  - token
  - lex
  - line_origin
  - skip
  - eat_kw
  - eat_op
  - take_ident
  - take_number
  - take_char
  - take_string
  - parse_ident
  - parse_u64
  - word
  - number
depends_on:
  - compiler-pipeline
  - string-parsing-algorithms
related:
  - parsing
  - semantic-analysis
  - chrisc-clvm
  - kcc
  - chrisasm
  - clvm-bytecode
---

# Lexical analysis

## Scope

Lexical analysis is the boundary between raw source characters and the syntactic units consumed by a parser.

In a conventional compiler the lexer usually turns:

~~~text
int total = value + 42;
~~~

into something conceptually like:

~~~text
KW_INT  IDENT(total)  '='  IDENT(value)  '+'  INTEGER(42)  ';'
~~~

ChrisOS currently implements this boundary in more than one way.

The most important distinction is:

- **ChrisC has an explicit lexer** that materializes a fixed array of \`Token\` records before parsing.
- **KCC does not have a separate token stream**. Its parser scans preprocessed source on demand with helpers such as \`eat_kw\`, \`eat_op\`, \`take_ident\` and \`take_number\`.
- **ChrisAsm and CLASM** use smaller line-oriented scanners appropriate to assembly syntax.

This chapter documents those concrete implementations rather than treating lexical analysis as one abstract subsystem.

![Lexical analysis paths in ChrisOS](../../assets/diagrams/lexical-analysis-en.svg)

## What belongs to lexical analysis

A lexer normally decides:

- where one token ends and another begins;
- which character sequences are identifiers;
- which identifiers are reserved keywords;
- how numeric literals are decoded;
- how string and character literals are decoded;
- which operator spelling wins when prefixes overlap;
- how comments and whitespace are discarded;
- which source location is attached to a token;
- when malformed character sequences become lexical errors.

It does **not** normally decide whether:

- a variable is declared;
- an expression has the correct type;
- a function has the correct argument count;
- a control-flow statement is legal in its context.

Those belong to parsing and semantic analysis.

## ChrisC: explicit tokenization

The ChrisC lexer is implemented inside:

~~~text
compiler/chrisc/chrisc.c
~~~

Its public compiler API hides the lexer, but the compilation flow eventually calls:

~~~text
lex(c, expanded_source, expanded_size)
~~~

after preprocessing has produced the combined translation unit.

The parser therefore receives a materialized token array rather than rescanning source text repeatedly.

## Token representation

ChrisC defines:

~~~text
typedef struct Token {
    TokenKind kind;
    int32_t value;
    int line, column;
    char name[NAME_MAX];
} Token;
~~~

The current compiler reserves:

~~~text
TOK_MAX = 262144
NAME_MAX = 48
~~~

so one compilation can hold at most 262,144 token records and an identifier spelling has at most 47 stored characters plus the terminating NUL.

If the token array is full, token creation fails with:

~~~text
too many tokens
~~~

## Source coordinates

The lexer tracks:

~~~text
line
column
~~~

while walking the expanded translation-unit buffer.

Every token records the line and the starting column at which it was recognized.

Preprocessing can combine files, so the compiler also keeps line-origin mappings.

When diagnostics are emitted, \`line_origin\` maps expanded-unit line numbers back to the original source file and source line.

This is the bridge between the expanded translation unit and user-visible \`file:line:column\` diagnostics.

## Character classes

ChrisC uses small ASCII-specific predicates.

An identifier can begin with:

- underscore;
- \`a-z\`;
- \`A-Z\`.

Subsequent characters may additionally contain digits.

The current lexer is therefore ASCII-oriented.

It does not implement Unicode identifier categories.

## Identifier length

While scanning an identifier, ChrisC rejects a spelling that would exceed \`NAME_MAX - 1\`.

The error is:

~~~text
identifier too long
~~~

This is safer than silently truncating the identifier because two distinct long names cannot collapse to the same stored spelling.

## Keyword recognition

After collecting an identifier spelling, ChrisC passes it through:

~~~text
keyword(name)
~~~

The lookup is exact and case-sensitive.

Recognized words map directly to specialized token kinds.

Examples include:

~~~text
void
int
float
char
struct
if
else
while
for
return
break
continue
long
short
unsigned
signed
const
static
extern
volatile
enum
union
typedef
switch
case
default
do
goto
sizeof
asm
_Generic
_Static_assert
_Alignas
_Alignof
_Bool
restrict
_Noreturn
_Thread_local
_Complex
~~~

There are also project-specific compatibility choices.

For example:

- \`double\` currently maps to the same \`T_FLOAT\` token as \`float\`;
- \`bool\` maps with \`_Bool\`;
- \`register\` and \`auto\` are accepted through the same token path currently used for \`inline\`.

Those choices are language-profile behavior, not evidence of full ISO C semantic equivalence.

## Non-keyword identifiers

If \`keyword\` finds no reserved spelling, the token kind remains:

~~~text
T_ID
~~~

The identifier text is copied into the token’s \`name\` field.

Whether that identifier later denotes a variable, typedef, enum constant, function, member or builtin is decided after lexing.

## Whitespace

ChrisC skips spaces, tabs, carriage returns and newlines.

Newline increments the line counter and resets the column to one.

Whitespace is therefore not represented as parser-visible tokens.

## Comments

The lexer recognizes both:

~~~text
// line comment
/* block comment */
~~~

Line comments run to newline.

Block comments run until the first closing \`*/\`.

Nested block comments are not implemented.

If EOF is reached before a closing delimiter, lexing fails with:

~~~text
unterminated comment
~~~

Although preprocessing also performs source transformation, comment recognition remains present in the explicit ChrisC lexer.

## String literals

When the lexer sees a double quote, it stores decoded bytes in the compiler’s string pool.

The current pool limit is:

~~~text
STR_POOL_MAX = 131072
~~~

A token does not contain the whole string.

Instead, its \`value\` field stores the starting offset into the shared string pool.

## String escapes

ChrisC currently recognizes these special escapes in strings:

~~~text
\\n
\\t
\\0
~~~

For another escaped character, the byte following the backslash is inserted directly.

Full C escape syntax such as arbitrary octal, hexadecimal and universal-character escapes is not implemented by this lexer.

## Adjacent string concatenation

After closing one string literal, the lexer skips horizontal whitespace and newlines.

If the next non-whitespace character is another quote, it continues appending to the same string-pool entry.

Thus:

~~~text
"abc"
"def"
~~~

is lexically combined into one string payload.

The final payload is NUL-terminated once the run of adjacent literals ends.

## Unterminated strings

A newline or end of source before a closing quote produces:

~~~text
unterminated string
~~~

If the shared pool fills, lexing fails with:

~~~text
string pool full
~~~

These failures occur before parsing.

## Character literals

A character literal becomes:

~~~text
T_NUM
~~~

with the byte value stored in \`value\`.

Recognized special escapes are:

~~~text
\\n
\\t
\\0
~~~

Other escaped characters become the escaped byte itself.

Missing closing syntax causes:

~~~text
unterminated char
~~~

The current model is a one-byte character-literal model, not the complete C multicharacter/wide/universal literal grammar.

## Integer literals

ChrisC recognizes decimal integers and hexadecimal integers beginning with \`0x\` or \`0X\`.

A leading zero without \`x\` does **not** switch the scanner into octal mode.

The accumulation limit is:

~~~text
0xffffffff
~~~

and overflow produces:

~~~text
integer literal overflow
~~~

## Integer suffixes

After the digits, ChrisC consumes repeated:

~~~text
u U l L
~~~

characters.

The suffix does not create a richer literal-type object in the token. The token still stores one 32-bit value field; later stages interpret type context.

## Malformed hexadecimal integers

A source fragment such as:

~~~text
0x
~~~

contains no valid hexadecimal digit and produces:

~~~text
bad integer literal
~~~

rather than a zero token.

## Floating literals

ChrisC supports a compact decimal float syntax.

Examples recognized by the scanner structure include:

~~~text
1.5
0.25
.75
1.
~~~

The host \`float\` bit pattern is stored in the token’s 32-bit \`value\`.

Important current omissions include:

- exponent notation such as \`1e6\`;
- hexadecimal floating syntax;
- a distinct double-precision literal representation.

These are language-profile limits.

## Operators and maximal matching

Many operators share prefixes:

~~~text
+
++
+=
~~~

and:

~~~text
<
<=
<<
<<=
~~~

The explicit lexer tests longer forms before shorter forms in each operator branch.

Supported multi-character forms include:

~~~text
++
--
->
...
==
!=
&&
||
<<
>>
+=
-=
*=
/=
%=
&=
|=
^=
<<=
>>=
<=
>=
~~~

The parser therefore receives the intended token rather than reconstructing operator boundaries itself.

## Punctuation

Single-character punctuation includes token forms for:

~~~text
( ) { } [ ]
; ,
? :
~
+ - . * / %
= ! & | ^ < >
~~~

## Invalid characters

Any character that does not match whitespace, comment syntax, identifier, literal or known operator/punctuation causes:

~~~text
invalid character
~~~

The compiler does not silently discard unknown bytes.

## End-of-file token

After scanning source, ChrisC appends:

~~~text
T_EOF
~~~

with the current line and column.

The parser can therefore recognize normal end-of-input through the token stream.

## Cooperative yielding

The lexer calls:

~~~text
maybe_yield()
~~~

inside its main loop.

If the surrounding compiler integration installed a yield callback, long lexical work periodically returns control to that callback.

This is cooperative progress behavior, not parallel lexing.

## ChrisC lexical diagnostics

Important lexical failures include:

~~~text
source size outside limit
unterminated comment
identifier too long
string pool full
unterminated string
unterminated char
integer literal overflow
bad integer literal
invalid character
too many tokens
~~~

Because source-origin mappings are retained, those failures can be mapped back to original files in expanded/include-heavy builds.

## KCC: scanning on demand

KCC takes a different architectural approach.

After preprocessing, it sets:

~~~text
g_p
~~~

to the preprocessed buffer.

Parser functions inspect and advance this pointer directly.

There is no \`Token[]\` stage between KCC preprocessing and parsing.

The lexical boundary is distributed across helper functions.

## KCC preprocessing before scanning

KCC preprocessing reads logical lines, handles continuations, strips comments, processes directives, expands macros, resolves includes and writes \`#line\` markers into the output stream.

The parser-side scanner therefore sees already-preprocessed source.

## \`skip\`

KCC’s:

~~~text
skip()
~~~

consumes spaces, tabs, carriage returns and newlines.

It also consumes generated:

~~~text
#line ...
~~~

markers through \`parse_hash\`.

When a marker is processed, KCC updates \`g_file\` and \`g_line\`, preserving diagnostic provenance without storing a source span on every token.

## Keywords in KCC

KCC uses:

~~~text
eat_kw("...")
~~~

to recognize a keyword at the parser cursor.

It checks that the character after the candidate word is not an identifier character.

Therefore:

~~~text
intvalue
~~~

does not match:

~~~text
int
~~~

The parser itself decides which keyword is legal in the current grammar position.

## Operators in KCC

KCC uses:

~~~text
eat_op("...")
~~~

for operators and punctuation.

The helper performs direct string matching and advances \`g_p\` on success.

It does not enforce a token boundary after the operator.

Correct disambiguation of overlapping operators therefore depends on parser code checking spellings in a safe order.

That differs from ChrisC’s centralized maximal-munch lexer.

## KCC identifiers

\`take_ident\` accepts:

~~~text
[A-Za-z_][A-Za-z0-9_]*
~~~

It consumes the complete identifier from source.

However, only the prefix that fits in the caller-provided destination buffer is copied.

Unlike ChrisC, there is no dedicated lexical “identifier too long” error at this helper boundary.

Callers must therefore size name buffers appropriately, and very long source identifiers can be truncated in local representations.

## KCC integer literals

\`take_number\` accepts decimal and \`0x\`/\`0X\` hexadecimal integers plus repeated \`u/U/l/L\` suffix characters.

Accumulation is 64-bit.

Overflow produces:

~~~text
integer constant overflow
~~~

This is a wider lexical integer range than current ChrisC.

A leading zero without \`x\` still does not create octal mode.

## KCC floating literals

The current KCC primary-expression path calls \`take_number\`, \`take_char\`, \`take_string\` and identifier parsing.

There is no separate floating-literal scanner in the current source.

KCC has a \`TY_FLOAT\` type representation, but that does not mean its literal grammar is equivalent to ChrisC’s \`T_FNUM\` path.

## KCC character literals

\`take_char\` supports one byte and special handling for:

~~~text
\\n
\\r
\\0
~~~

The helper consumes a closing quote if one is present.

At the helper level, however, reaching source end without the closing quote does not directly produce an “unterminated char” diagnostic.

A later parser failure may expose malformed input, but lexical validation is less centralized than in ChrisC.

## KCC strings

\`take_string\` decodes:

~~~text
\\n
\\r
\\t
\\0
~~~

and copies into a caller-provided buffer.

It tracks the decoded length even if it exceeds the output capacity, allowing a caller to reject an oversized use.

The helper does not itself reject end-of-input before a closing quote.

## Comment handling in KCC

KCC removes comments during preprocessing through:

~~~text
strip_comments
~~~

It supports line comments and block comments, with block-comment state carried across logical lines.

Double-quoted strings are tracked so comment delimiters inside those strings are not treated as comments.

This happens before parser-side scanner helpers run.

## Generated line markers

The preprocessor emits markers such as:

~~~text
#line 120 "kernel/metal/example.c"
~~~

into \`g_pp\`.

\`skip\` consumes those markers and updates current file/line state.

This replaces the per-token source coordinate model used by ChrisC.

## Explicit token stream versus scanner-on-demand

### ChrisC advantages

An explicit token stream gives:

- centralized lexical rules;
- one maximal-munch implementation;
- stable line/column per token;
- parser lookahead independent of raw character scanning;
- clear lexical error boundaries.

Costs include a separate scan, token memory and a fixed token-count ceiling.

### KCC advantages

Scanner-on-demand reduces token-storage overhead and makes small project-specific parser helpers simple.

Costs include:

- tighter lexer/parser coupling;
- parser-sensitive operator ordering;
- distributed malformed-input handling;
- weaker long-identifier enforcement;
- less centralized diagnostics.

## ChrisAsm scanner

ChrisAsm is line-oriented.

Its \`parse_ident\` reads until whitespace or assembly delimiters such as:

~~~text
, : ; [ ] + -
~~~

The resulting spelling can denote a mnemonic, register, symbol or directive depending on parser context.

## ChrisAsm numbers

\`parse_u64\` accepts decimal and \`0x\` hexadecimal spellings and checks 64-bit overflow.

This is an assembler-operand scanner, not a C literal grammar.

## ChrisAsm comments

At line start, after whitespace, a line beginning with:

~~~text
#
;
~~~

is ignored.

Semicolon also acts as a parser delimiter in instruction syntax.

The lexical rules are intentionally smaller than the C-family scanners.

## CLASM scanner

The CLVM assembler uses another small line scanner.

\`word\` accepts:

~~~text
[A-Za-z_][A-Za-z0-9_]*
~~~

for instruction and label names.

Instruction/label comparison is case-insensitive, unlike ChrisC/KCC identifiers.

## CLASM numbers

\`number\` accepts optional minus, decimal and hexadecimal input and accumulates into a 32-bit value.

Its result is used as \`int32_t\` instruction data.

This grammar is designed for VM operands.

## CLASM comments and trailing text

A line tail is empty if it contains whitespace or begins with:

~~~text
;
#
~~~

Unexpected extra operand text is rejected by \`parse_line\`.

CLASM therefore combines small lexical helpers and grammar validation closely.

## Validation evidence

\`tools/test_chrisc_c17.c\` exercises macros, identifiers, literals, operators and many C-like keywords through compile-and-run behavior.

\`tools/test_fuzz_chrisc.c\` submits deterministic pseudo-random printable source, checks documented success/failure behavior and verifies the compiler still accepts a known-good program afterward.

\`tools/test_kcc.c\` compiles fixtures and real kernel sources, indirectly exercising KCC preprocessing and scanning across a broad source corpus.

\`tools/test_chrisasm.c\` checks accepted assembly, unknown mnemonic rejection and relocation-producing symbol references.

\`tools/test_clasm.c\` checks labels, instructions, integer operands and CLVM bytecode emission.

## Missing lexical tests

The current tree does not have a dedicated table-driven ChrisC lexer suite covering every spelling and error.

Useful missing cases include:

- every keyword;
- every multi-character operator;
- maximal-munch conflicts;
- identifier length boundary;
- integer overflow boundary;
- malformed \`0x\`;
- adjacent strings across lines;
- every supported escape;
- unsupported escape behavior;
- unterminated comment/string/char;
- invalid non-ASCII bytes;
- token-count boundary;
- KCC long-identifier truncation;
- KCC unterminated string/char behavior;
- KCC operator-prefix ordering;
- source-position preservation across nested include/macro expansion.

## Security and robustness

Lexers and scanners frequently process untrusted text.

Relevant failure classes include:

- integer overflow;
- buffer overflow;
- malformed escapes;
- unterminated delimiters;
- source-bound errors;
- comment/string confusion;
- ambiguous operator matching;
- pathological rescanning.

ChrisC handles many of these centrally with explicit bounds and hard lexical errors.

KCC uses bounded buffers throughout much of its implementation, but malformed-input behavior is distributed among preprocessing, scanner helpers and parser callers.

Neither compiler should be described as a hardened hostile-input parser without dedicated adversarial testing.

## Complexity

ChrisC’s explicit lexer is fundamentally:

~~~text
O(n)
~~~

in expanded source length for the primary scan.

Keyword lookup is a short chain of exact string comparisons.

KCC has no one lexical pass. Its scanning cost is distributed through parser operations and lookahead.

Most scanning advances forward, but some parser helpers save and restore \`g_p\`, so lexical cost and grammar behavior are coupled.

## Current limitations

At the documented revision:

- ChrisC identifiers are ASCII-only;
- ChrisC identifier storage is limited to 47 characters;
- ChrisC integer lexical values are limited to 32 bits;
- ChrisC supports decimal/hex integers but no octal mode;
- ChrisC float syntax lacks exponent and hexadecimal-float forms;
- ChrisC string/char escapes are a small subset;
- ChrisC uses fixed token and string-pool ceilings;
- KCC has no independent token stream;
- KCC operator matching depends on parser ordering;
- KCC identifiers can be truncated to destination buffers;
- KCC primary-expression scanning has no general float-literal scanner;
- KCC string/char helpers do not directly reject missing closing quotes;
- ChrisAsm and CLASM intentionally use narrower assembly-specific scanners;
- there is no unified lexer library across the language toolchain.

## Roadmap boundary

A stronger lexical layer could add:

- explicit language-profile specifications;
- table-driven keyword/operator definitions;
- reusable source-span structures;
- an explicit UTF-8/Unicode policy;
- complete numeric-literal grammar for each supported C profile;
- complete escape grammar;
- standalone lexical tests;
- property-based and coverage-guided fuzzing;
- structured lexical error codes;
- a reentrant KCC scanner context;
- clearer KCC scanner/parser separation;
- source spans preserved through macro expansion.

These remain roadmap items until implemented and validated.

## Source map and revision note

The explicit ChrisC lexer, token kinds, storage and source-position logic are in \`compiler/chrisc/chrisc.c\`. KCC’s scanner-on-demand helpers and preprocessing path are in \`compiler/kcc/kcc.c\`. ChrisAsm scanning lives in \`compiler/chrisasm/chrisasm.c\`, and the CLVM assembler scanner is in \`compiler/clvm/clasm.c\`.

All current-behavior claims in this chapter were reconciled against ChrisOS revision \`e05a17fd76333114a3fb5c2452f38ca747d4ac56\`.
