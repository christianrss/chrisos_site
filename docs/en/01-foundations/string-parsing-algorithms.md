---
id: string-parsing-algorithms
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: 92fb561574bd929522ea005b9fd433138bea3236
sources:
  - kernel/metal/string.c
  - LIB/STRING.CC
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_pub.h
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - tools/test_shader.c
symbols:
  - strstr
  - sh_lex
  - push_tok
  - sync_stmt
  - parse_primary
  - parse_unary
  - parse_bin
  - parse_expr
  - parse_binary
  - parse_ident
  - parse_u64
depends_on:
  - data-representation-layout
  - algorithmic-complexity
  - recursion-recurrences-amortization
  - sorting-searching
related:
  - systems-algorithms
  - compiler-pipeline
  - lexical-analysis
  - parsing
  - shaders-csir
---

# String and parsing algorithms

<div class="abstract">
Strings, token streams and syntax trees are different representations of the same fundamental problem: interpreting ordered symbols under explicit rules. This chapter develops byte-string matching, prefix functions, rolling hashes, lexical scanning, finite-state recognition, context-free grammars, recursive descent, precedence climbing, associativity and parser recovery. It then reconciles those ideas with the current ChrisOS source. The kernel and ChrisC string libraries implement direct substring scans rather than KMP or Boyer-Moore; the shader frontend uses a bounded linear lexer followed by recursive-descent and precedence-climbing parsing; KCC contains a separate precedence-based expression parser with short-circuit code generation; and ChrisASM parses its compact textual grammar directly through pointer-scanning helpers. The distinction between general theory and source-proven implementation is maintained throughout.
</div>

## Strings are representations, not abstract text by default

A string algorithm operates on a sequence

~~~text
S = s[0], s[1], ..., s[n-1]
~~~

drawn from an alphabet. The alphabet may be bytes, Unicode code points, tokens or another discrete symbol set. Complexity statements are only meaningful when the representation is stated.

The current low-level ChrisOS string routines operate on zero-terminated byte strings. They do not perform Unicode normalization, grapheme segmentation or locale-sensitive collation. Therefore an operation such as equality means equality of the represented byte sequence, not linguistic equivalence.

This matters because visually identical text may have different encoded forms. A systems routine that compares path names, identifiers or protocol fields must use the contract required by that subsystem rather than assume that "text equality" has a universal meaning.

## Exact equality, prefix comparison and substring search

Three common contracts are distinct.

Exact equality asks whether:

~~~text
|A| = |B|
and
A[i] = B[i] for every valid i
~~~

Prefix comparison asks how two sequences order when scanning from the beginning. Substring search asks whether a pattern P of length m occurs at some offset of text T of length n:

~~~text
T[i + j] = P[j] for every j in [0, m)
~~~

for at least one candidate i.

A direct substring algorithm tries each candidate start and compares pattern symbols until mismatch or full match.

~~~text
for i = 0 .. n-m:
    j = 0
    while j < m and T[i+j] == P[j]:
        j++
    if j == m:
        return i
return not_found
~~~

Worst-case time is O(nm), with O(1) auxiliary state.

Inputs such as repeated prefixes can approach that bound because much of the pattern is compared again at many adjacent positions.

## Current kernel strstr

The current <code>kernel/metal/string.c::strstr</code> follows the direct algorithm.

It first handles the empty pattern, computes the pattern length, then advances the haystack one byte at a time. At every candidate it compares successive bytes until either a mismatch occurs or the full pattern length is reached.

The relevant control-flow shape is:

~~~text
while haystack is not at NUL:
    i = 0
    while i < pattern_length and haystack[i] == pattern[i]:
        i++
    if i == pattern_length:
        return current haystack
    haystack++
~~~

The auxiliary state is constant. If the remaining text contains many prefixes of the pattern, the same text positions can participate in repeated comparisons.

No prefix table, bad-character table, suffix automaton or rolling hash is constructed in this routine. Therefore the source establishes direct matching, not KMP, Boyer-Moore or Rabin-Karp.

## Current ChrisC library strstr

<code>LIB/STRING.CC::strstr</code> implements the same asymptotic strategy with a different decomposition.

It computes the needle length, iterates the candidate offset <code>i</code>, and calls <code>strncmp(h + i, n, ln)</code> for each candidate.

Conceptually:

~~~text
i = 0
while h[i] != NUL:
    if prefix_equal(h+i, needle, needle_length):
        return h+i
    i++
~~~

The nested prefix comparison gives the same O(nm) worst-case bound. This is important when documenting the runtime: a helper decomposition does not change the algorithmic class.

## Prefix functions and KMP

Knuth-Morris-Pratt avoids rechecking text characters after a mismatch by precomputing structure in the pattern.

Define the prefix function for each pattern position as the length of the longest proper prefix of the pattern prefix that is also a suffix. A failure transition then says how much of the already matched prefix remains useful.

For pattern length m:

~~~text
preprocessing = O(m)
search        = O(n)
total         = O(n + m)
extra memory  = O(m)
~~~

The key invariant is that after processing text through position i, the state records the length of the longest pattern prefix that is also a suffix of the processed text.

KMP is valuable when worst-case linear matching matters. Its extra table and less trivial control flow may be unnecessary for short strings or rarely executed paths.

The reviewed ChrisOS string routines do not currently implement KMP. It is included here as an algorithmic foundation and a possible design alternative.

## Boyer-Moore and Horspool

Boyer-Moore compares from the pattern's end and uses mismatch information to skip candidate starts. Full Boyer-Moore combines bad-character and good-suffix rules. Horspool keeps a simpler bad-character-style shift table.

These approaches can skip large portions of ordinary text and perform very well in practice, especially for longer patterns and reasonably large alphabets. Their worst-case guarantees depend on the exact variant.

They also require preprocessing and tables whose cost may dominate tiny kernel strings. Again, no such table is established by the reviewed <code>strstr</code> implementations.

## Rabin-Karp and rolling hashes

Rabin-Karp maps a window to a rolling hash. When the window moves by one symbol, the next hash is updated without recomputing the whole window.

A hash match is only a candidate. Unless collision-free arithmetic is proven for the domain, the underlying bytes must be compared before accepting equality.

This is useful for multiple-pattern or repeated-window workloads, but it introduces arithmetic, collision reasoning and sometimes modulus cost. Hash equality must never silently become semantic equality.

## Tokenization changes the alphabet

A compiler normally does not parse raw source characters directly at every grammar production. Lexical analysis maps character sequences into tokens:

~~~text
source bytes
    |
    v
lexer
    |
    v
IDENT  PLUS  INT  SEMI  ...
~~~

A token can carry:

- kind;
- source offset;
- length;
- line and column;
- decoded numeric value;
- interned or referenced spelling.

The parser then consumes token kinds rather than rediscovering character classes repeatedly.

This separation reduces grammar complexity and centralizes rules for identifiers, literals, comments, whitespace and operators.

## Deterministic lexical scanning

A conventional lexer can be viewed as a deterministic finite-state machine. For each input symbol, the current lexical state and symbol determine the next state.

For a source of n bytes, a lexer that advances monotonically and performs bounded work per byte is O(n). Some token classes require local lookahead, but the overall scanner can remain linear if it never retreats over unbounded input.

The maximal-munch rule usually selects the longest valid token beginning at the current position. This is why a scanner should prefer <code>>=</code> over <code>></code> when both begin at the same byte.

Lexical correctness has three layers:

1. every accepted byte belongs to exactly the intended tokenization;
2. invalid input produces a diagnostic rather than an accidental token;
3. source positions remain accurate enough for later diagnostics.

## The ChrisOS shader lexer

The current shader frontend provides a concrete bounded lexer in <code>kernel/gfx/shader/sh_lex.c</code>.

<code>sh_lex</code> scans the source with an integer offset and tracks line and column. It recognizes whitespace, newlines, supported directives, identifiers and keywords, numeric forms, punctuation and multi-character operators.

Keyword recognition uses a fixed table. The source includes names such as:

~~~text
in
out
uniform
const
layout
void
bool
int
float
vec2
vec3
vec4
mat3
mat4
sampler2D
if
else
for
return
discard
true
false
~~~

Unknown characters are emitted as <code>TK_BAD</code>, an "invalid token" diagnostic is recorded, and scanning continues so the frontend can retain useful diagnostics rather than dereference invalid state.

At the end, the lexer appends an explicit EOF token.

## Bounded lexical resources

The shader frontend is intentionally bounded.

The reviewed headers establish:

| Resource | Bound |
|---|---:|
| shader source | 4096 bytes |
| token array | 768 tokens |
| AST | 512 nodes |
| parser nesting | 32 levels |

The source-length check occurs before lexical scanning. <code>push_tok</code> rejects a token once <code>SH_TOK_MAX</code> would be exceeded.

These are not merely implementation details. They are resource contracts that bound memory use and reduce denial-of-service exposure in a kernel-resident parser.

A fixed array also changes failure behavior: exhaustion must produce an explicit error rather than silently overwrite adjacent state.

## From tokens to grammar

Lexing answers "what symbols are present?" Parsing answers "how are those symbols structurally related?"

A context-free grammar describes productions such as:

~~~text
expr   -> expr + term | term
term   -> term * unary | unary
unary  -> - unary | primary
primary -> IDENT | NUMBER | ( expr )
~~~

The grammar as written is left recursive. A naive recursive-descent implementation cannot directly implement <code>expr -> expr + term</code> because the function would recurse before consuming input.

Practical handwritten parsers therefore refactor the grammar or use a precedence algorithm.

## Recursive descent

Recursive descent maps grammar structure to procedures.

Typical functions include:

~~~text
parse_primary
parse_unary
parse_statement
parse_block
parse_function
~~~

The central invariant is progress: successful parsing consumes the tokens corresponding to the accepted construct; failure must either leave a documented recovery position or advance to a synchronization boundary.

Unbounded recursive descent over attacker-controlled nesting can overflow the machine stack. A nesting guard is therefore part of parser correctness in low-level software, not merely an optimization.

## Precedence and associativity

Expression parsing must encode the fact that:

~~~text
a + b * c
~~~

means:

~~~text
a + (b * c)
~~~

rather than:

~~~text
(a + b) * c
~~~

Operators receive precedence levels. Associativity determines how operators at the same precedence group.

For a left-associative binary operator:

~~~text
a - b - c
~~~

means:

~~~text
(a - b) - c
~~~

A precedence-climbing parser accepts a minimum precedence and recursively parses a right operand using a stricter minimum for left-associative operators.

## Shader precedence climbing

The shader parser in <code>kernel/gfx/shader/sh_parse.c</code> implements this pattern in <code>parse_bin</code>.

Its table orders:

- logical OR;
- logical AND;
- equality;
- relational comparisons;
- addition and subtraction;
- multiplication, division and remainder.

The function first parses a unary expression. It then examines the next binary operator. If the operator's precedence is below the current minimum, the loop ends. Otherwise it consumes the operator and calls:

~~~text
parse_bin(right, precedence + 1)
~~~

before constructing the binary AST node.

The <code>+1</code> rule makes the current table left associative. Higher-precedence operators bind inside the recursive right operand before the lower-precedence node is completed.

<code>parse_expr</code> starts the process with minimum precedence 1.

This is precedence climbing. It should not be described as a generic Pratt parser because the current source does not expose Pratt-style null-denotation and left-denotation dispatch tables.

## Primary, postfix and unary structure

The same parser separates layers.

<code>parse_primary</code> handles literals, identifiers, calls, constructors and parenthesized expressions.

A postfix pass handles constructs that bind tightly after a primary. <code>parse_unary</code> handles prefix operators such as plus, minus, logical NOT and increment/decrement before falling through to primary parsing.

This decomposition establishes an effective precedence hierarchy:

~~~text
primary / postfix
        |
      unary
        |
      binary precedence levels
        |
     expression
~~~

The hierarchy is structural. It avoids a giant conditional parser that mixes all binding rules in one state machine.

## AST allocation as a parser invariant

The parser does not allocate arbitrary heap nodes while parsing. <code>node_new</code> uses the bounded AST array in the compilation context.

Before creating a node it checks <code>SH_AST_MAX</code>. Every new node receives initialized child links and metadata.

Therefore one parser invariant is:

~~~text
0 <= nast <= SH_AST_MAX
~~~

and no valid AST index may refer beyond the initialized prefix.

When the capacity is exhausted, parsing reports an error instead of corrupting memory.

## Nesting control

<code>enter</code> checks whether the parser depth has reached <code>SH_NEST_MAX</code>. The current limit is 32.

This bounds recursive paths through nested expressions and constructs. The exact host stack consumption per level is compiler-dependent, but the logical parser recursion is explicitly capped.

A parser that validates syntax but permits unbounded nesting is not robust enough for hostile input in a privileged runtime.

## Error recovery and synchronization

Stopping at the first syntax error is simple but can produce poor diagnostics. Continuing without a recovery rule is worse because one malformed token can cascade into arbitrary parser state.

The shader parser uses <code>sync_stmt</code> as a synchronization routine. It advances until a plausible statement boundary while tracking brace depth.

Its recovery boundary includes:

- semicolon at the current brace depth;
- a closing brace that belongs to the surrounding context;
- EOF.

This is a form of panic-mode recovery.

The objective is not to pretend malformed source is valid. The objective is to restore a parser state from which subsequent diagnostics are meaningful.

## The KCC expression parser

KCC has a separate parser implementation in <code>compiler/kcc/kcc.c</code>.

<code>parse_expr</code> calls <code>parse_binary(out, 0)</code>. The binary parser maintains explicit operator and precedence tables covering logical, bitwise, equality, relational, shift, additive and multiplicative operators.

It parses unary input first, then chooses an operator whose precedence satisfies the current threshold and recursively parses the right operand with <code>prec_of[matched] + 1</code>.

The KCC path additionally integrates code generation. Logical AND and OR receive short-circuit control flow: the left operand can determine the result without evaluating the right operand.

This shows why parsing cannot be documented only as grammar recognition in a compiler. The parser's associativity and evaluation strategy constrain emitted control flow.

The shader and KCC parsers are separate implementations. Similar algorithmic structure does not imply shared code.

## Direct parsing in ChrisASM

ChrisASM demonstrates another legitimate design.

Its syntax is sufficiently compact that <code>compiler/chrisasm/chrisasm.c</code> uses pointer-scanning helpers rather than first materializing a general token array.

<code>skip_ws</code> advances across whitespace. <code>parse_ident</code> copies a token-like field until delimiters such as comma, colon, semicolon, brackets or signs. <code>parse_u64</code> recognizes decimal and hexadecimal integer forms.

The integer parser includes an overflow check before:

~~~text
value = value * base + digit
~~~

using the equivalent safety condition:

~~~text
value <= (UINT64_MAX - digit) / base
~~~

This prevents wraparound from converting an invalid literal into an accepted but different numeric value.

A separate token array would add structure, but it is not automatically superior for a small grammar. The appropriate representation depends on grammar complexity, diagnostics, reuse and extension pressure.

## Parser correctness properties

A systems parser should be reasoned about through explicit properties.

### Progress

Every successful loop iteration must consume input or transition to termination. Otherwise malformed input can cause an infinite loop.

### Bounded access

Lookahead must prove that the inspected byte or token exists. Sentinel EOF tokens can simplify this invariant, but they do not remove array-bound requirements.

### Determinism

For a deterministic grammar and parser state, the same token stream must yield the same parse result. Hidden global mutation can violate this property.

### Complete consumption

A parser for a complete unit should normally reject unexplained trailing tokens rather than silently accept a valid prefix.

### Resource bounds

Input length, token count, AST count and recursion depth must have defined saturation behavior.

### Diagnostic locality

Errors should retain source position and identify the violated expectation without accessing already-invalid nodes.

## Complexity model

For a well-designed lexer over n source bytes:

~~~text
time = O(n)
space = O(number_of_tokens)
~~~

For deterministic recursive descent over t tokens, parsing is often O(t), provided productions do not repeatedly rescan large token prefixes.

Precedence climbing visits each expression token a bounded number of times, giving O(t) time for the expression under a fixed operator table.

Error recovery can alter practical cost, but a synchronization scan that only moves forward remains linear across the failed region.

By contrast, naive substring search remains O(nm) in the worst case because candidate comparisons overlap.

These costs should not be collapsed into a generic statement that "parsing is linear." The representation and recovery policy determine the actual bound.

## Memory ownership and lifetime

String and parser code needs clear ownership even when it performs no heap allocation.

A view into a source buffer is only valid while the backing buffer remains alive and unchanged in ways that would invalidate offsets.

The shader frontend copies source into a bounded compilation context and records offsets into that representation. Tokens and AST nodes live inside the same bounded context, which simplifies lifetime relationships.

ChrisASM's pointer-scanning helpers instead advance through a caller-provided textual representation while copying selected fields into fixed local buffers.

The two designs have different lifetime risks even when both avoid general dynamic allocation.

## Concurrency

A parser is naturally reentrant only when all mutable parse state belongs to the invocation or an explicitly owned context.

The shader frontend's <code>ShComp</code> model concentrates token, AST and parser counters in a compilation context, which supports reasoning about per-compilation state.

KCC and ChrisASM also contain broader compiler-global state, so this chapter does not claim that those complete compilers are safely reentrant or parallel merely because individual parsing routines have local variables.

Concurrency claims require source evidence for global state, synchronization and lifetime; parser theory alone cannot establish them.

## Security boundaries

Parsers process structured input and therefore sit on an attack surface whenever input is untrusted.

Relevant failure classes include:

- buffer overrun from token spelling;
- integer overflow in literal conversion;
- recursion exhaustion from deep nesting;
- token or AST capacity overflow;
- quadratic or worse adversarial behavior;
- accepting invalid trailing input;
- malformed recovery that loops without progress;
- use-after-free of source-backed slices;
- ambiguity that creates implementation-dependent interpretation.

The shader limits and ChrisASM integer-overflow check directly address specific members of this list.

They do not prove the absence of all parser vulnerabilities.

## Validation strategy

Algorithmic validation should include independent invariants rather than only a few happy-path examples.

For substring search:

- empty pattern;
- empty text;
- match at first position;
- match at final position;
- no match;
- repeated-prefix adversarial text;
- pattern longer than text.

For lexical analysis:

- each supported operator;
- ambiguous operator prefixes;
- whitespace and line transitions;
- invalid bytes;
- capacity boundaries;
- source coordinates.

For expression parsing:

- every precedence boundary;
- left associativity;
- parenthesized override;
- unary versus binary binding;
- malformed operand;
- missing delimiter;
- nesting limit.

For numeric parsing:

- zero;
- maximum valid value;
- first overflowing value;
- invalid digit for base;
- prefix with no digits.

The repository's deterministic documentation checker for this chapter additionally verifies model KMP/direct matching and source anchors. Existing <code>tools/test_shader.c</code> provides executable shader-frontend coverage, including rejected syntax and diagnostics.

## Current implementation boundary

At ChrisOS revision 92fb561574bd929522ea005b9fd433138bea3236, the inspected source establishes:

- direct O(nm) worst-case substring matching in kernel <code>strstr</code>;
- direct prefix-at-each-position matching in ChrisC <code>strstr</code>;
- a bounded shader lexer with source coordinates, explicit EOF and token-capacity checks;
- a bounded shader AST and nesting depth;
- recursive-descent parsing for primary/unary/statement structure;
- precedence climbing for shader binary expressions;
- panic-style statement synchronization through <code>sync_stmt</code>;
- a separate precedence-based KCC binary-expression parser;
- short-circuit KCC handling for logical AND/OR;
- direct pointer-scanning helpers in ChrisASM;
- explicit unsigned 64-bit literal overflow rejection in ChrisASM.

The inspected source does not establish:

- KMP in the runtime string libraries;
- Boyer-Moore/Horspool in those libraries;
- Rabin-Karp substring search;
- a suffix tree, suffix array or suffix automaton for general text;
- a parser generator driving the shader or ChrisASM parsers;
- an unbounded/general GLSL parser;
- safe parallel compilation of all compiler frontends.

Those distinctions prevent textbook algorithms from being mislabeled as current ChrisOS behavior.

## Revision provenance

Implementation claims in this chapter were reconciled against ChrisOS <code>main</code> revision 92fb561574bd929522ea005b9fd433138bea3236.

The primary inspected files are:

- <code>kernel/metal/string.c</code>;
- <code>LIB/STRING.CC</code>;
- <code>kernel/gfx/shader/sh_lex.c</code>;
- <code>kernel/gfx/shader/sh_parse.c</code>;
- <code>kernel/gfx/shader/sh_int.h</code>;
- <code>kernel/gfx/shader/sh_pub.h</code>;
- <code>compiler/kcc/kcc.c</code>;
- <code>compiler/chrisasm/chrisasm.c</code>;
- <code>tools/test_shader.c</code>.

The chapter separates general algorithmic foundations from source-proven mechanisms and treats resource bounds, recovery and failure behavior as part of the parser contract rather than incidental details.
