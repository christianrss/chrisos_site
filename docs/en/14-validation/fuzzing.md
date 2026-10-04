---
id: fuzzing
lang: en
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - tools/test_fuzz_cfs.c
  - tools/test_fuzz_elf.c
  - tools/test_fuzz_chrisc.c
  - tools/test_fuzz_clvm.c
  - tools/test_elf_malformed.c
  - tools/test_shader.c
  - chrisvm/tests/test_chrisvm.c
symbols: []
depends_on:
  - host-tests
  - fault-injection
related:
  - performance-measurement
  - chrisfs
  - clvm
  - shader-pipeline
  - chrisvm
---

# Fuzzing parsers and formats

## Scope

ChrisOS already uses fuzz-like testing against several high-risk input boundaries.

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, the principal deterministic fuzz targets are:

- ChrisFS path/operation handling;
- ELF loader input;
- ChrisC source input;
- CLVM image parsing;
- ChrisVM instruction decoding;
- selected shader/CSI malformed-input cases.

The current system should be described precisely as **deterministic pseudo-random host fuzzing plus structured malformed-input tests**.

It is not yet a coverage-guided fuzzing platform.

There is no integrated libFuzzer/AFL-style engine, persistent corpus management, automatic minimization, mutation feedback loop or repository-wide coverage metric.

## Why these boundaries matter

A parser converts untrusted bytes or text into internal state.

The dangerous transition is:

[
	ext{untrusted input} ightarrow 	ext{trusted internal representation}
]

A bug at this boundary can cause:

- out-of-bounds memory access;
- integer overflow;
- stale state;
- resource leaks;
- invalid control flow;
- filesystem corruption;
- acceptance of malformed executable code.

For an operating-system project, parsers and binary formats are therefore high-value fuzz targets even before network exposure becomes broad.

## Deterministic pseudo-random generators

The dedicated fuzz tests use simple linear-congruential pseudo-random generators.

A representative recurrence is:

[
s_{n+1} = 1664525s_n + 1013904223 pmod{2^{32}}
]

Seeds are constants embedded in each test.

Examples include:

    0xC0FFEE
    0xC1A55E
    1

This has an important benefit: CI runs are reproducible.

The same revision executes the same generated sequence.

The disadvantage is equally important: repeated runs do not explore new input space unless the seed, generator or iteration count changes.

## Fuzzing versus random testing

The word "fuzzing" covers several levels of sophistication.

The current ChrisOS tests primarily use:

1. deterministic random byte/text generation;
2. hand-written malformed cases;
3. post-condition checks;
4. resource-cleanup invariants.

They do not currently use feedback from code coverage to evolve inputs.

Therefore the strongest claim is:

> ChrisOS exercises deterministic adversarial input sets in every normal host-gate run.

It should not claim exhaustive or coverage-guided fuzzing.

## ChrisFS fuzz target

`tools/test_fuzz_cfs.c` creates a memory-backed writable block device, formats ChrisFS and mounts it.

It then executes 200 iterations.

Each iteration generates a path of pseudo-random length:

    rnd() % 48

and fills it with printable-ish bytes.

For each generated path the test attempts:

    cfs_mkdir
    cfs_write
    cfs_read
    cfs_unlink

Return codes are intentionally not required to be success.

Malformed names are expected to be rejected.

The primary invariant is filesystem integrity after the adversarial sequence.

At the end:

    cfs_fsck(&fs)

must return `CFS_OK`.

## ChrisFS fuzz oracle

The ChrisFS test is not asking:

> Did every random operation succeed?

It asks:

> After valid and invalid operations were attempted, is the filesystem still structurally consistent?

That is a stronger oracle for parser/path robustness.

The current oracle could be improved by additionally checking:

- mount after remount;
- allocation bitmap conservation;
- absence of unreachable inodes/blocks;
- file-content persistence for a tracked valid subset;
- repeated fsck after simulated crashes.

## ELF fuzz target

`tools/test_fuzz_elf.c` generates 300 inputs.

Each input contains from 1 to 256 bytes.

The buffer is filled with pseudo-random data.

On approximately one eighth of iterations, the first four bytes are changed to:

    0x7f 'E' 'L' 'F'

This biases some cases deeper into the ELF parser rather than having every input fail immediately on magic.

That small amount of structure increases useful parser exploration.

## ELF resource-pressure oracle

The ELF fuzz target also limits the fake physical-page allocator.

Before each load:

    g_budget = 4

The test records the current allocation count and invokes the real `elf_load`.

Accepted return values are the loader's defined success/failure forms.

When loading fails, the test requires:

- allocated-page count restored to its previous value;
- current process restored to process 0.

This is a strong property because it detects cleanup bugs, not only crashes.

If a fuzz input drives the loader far enough to allocate state and then fail, every partial resource must still be released.

## Structured ELF malformed suite

`tools/test_elf_malformed.c` complements pseudo-random ELF fuzzing.

It contains named adversarial constructions for:

- truncation;
- bad magic;
- offset overflow;
- address overflow;
- `filesz > memsz`;
- overlapping segments;
- W+X;
- invalid entry point;
- unsupported program header;
- mid-load OOM.

This is not random fuzzing.

It is a regression corpus for known semantic invariants.

The two styles should coexist:

    random exploration + named invariant cases

A future coverage-guided engine should seed its corpus with these structured cases.

## ChrisC fuzz target

`tools/test_fuzz_chrisc.c` targets the ChrisC compiler frontend.

It performs 48 iterations.

Each source has pseudo-random length below 180 bytes and contains printable ASCII characters.

The compiler is called with a fixed output code buffer.

The accepted result is a normal compiler success/failure status.

Unexpected return codes fail the test.

After adversarial inputs, the test compiles a known-valid program:

    int main(){return 1;}

This final control case matters.

It checks that malformed earlier inputs did not leave global/compiler state corrupted enough to reject valid source.

## ChrisC limitations

The current ChrisC fuzzer is intentionally small.

It does not yet:

- preserve interesting inputs;
- understand grammar;
- mutate known-valid ChrisC programs;
- generate deep ASTs systematically;
- vary include graphs;
- target semantic/type edge cases;
- run under coverage feedback.

A grammar-aware mutator would substantially improve depth.

Random printable text often dies in lexical or early parse stages.

## CLVM format fuzz target

`tools/test_fuzz_clvm.c` performs 200 iterations over buffers up to 96 bytes.

For each generated buffer it calls:

    clvm_parse

The returned enum must remain within the defined `ClvmLoadError` range.

The corresponding error must also have a non-null diagnostic string.

After random inputs, the test constructs a valid CLVM image using:

    clvm_write_image

and verifies that the image parses successfully with the expected code size.

This establishes two invariants:

1. malformed input remains inside defined error semantics;
2. fuzz activity does not break the valid encode/decode path.

## ChrisVM decode fuzzing

`chrisvm/tests/test_chrisvm.c` contains `test_fuzz_decode`.

It performs 2000 deterministic iterations.

Each case creates between 1 and 15 random bytes and calls the ChrisVM instruction decoder.

The result must be either:

    -1

for invalid input, or a decoded length from 1 through 15 with:

    insn.len == return_value

The key invariant is bounded decoding.

The decoder must not claim an impossible x86 instruction length or return inconsistent metadata.

This target is valuable because decoder bugs can corrupt all higher emulator state.

## ChrisVM execution boundary

The decode fuzzer validates instruction decoding, not arbitrary instruction execution.

A byte sequence that decodes successfully is not automatically run through the full CPU/MMU/device model by this target.

Future work can separate:

- decode fuzzing;
- semantic instruction fuzzing;
- differential execution;
- MMU/page-fault fuzzing;
- device-register fuzzing.

Each has a different oracle.

## Shader and CSI adversarial cases

`tools/test_shader.c` contains a routine named `test_csi_guest_fuzz`.

The test first creates a valid shader/CSI representation and reloads it.

It then mutates serialized data and supplies a small set of deliberately bad shader sources and an oversized identifier-like input.

It also checks guest ownership behavior around shader handles.

This is best classified as **structured adversarial testing**, not broad pseudo-random fuzzing.

The overall shader suite finally verifies that live shader resources return to the original count.

That cleanup invariant is particularly important for repeated guest compilation.

## Gate integration

The four dedicated targets are:

    host-fuzz-cfs-test
    host-fuzz-elf-test
    host-fuzz-chrisc-test
    host-fuzz-clvm-test

They are dependencies of:

    host-gates

and also of:

    host-stress

Therefore these fuzz cases run as part of the broad host validation graph.

The shader adversarial cases run through:

    host-shader-test

which is also included in `host-gates`.

ChrisVM decode fuzzing belongs to the separate:

    make chrisvm-test

suite rather than the main `host-gates` dependency list.

## Gate audit

The host test graph is checked by:

    tools/check_test_gates.py

This helps prevent newly defined test targets from becoming disconnected from the aggregate host gate.

However, the audit verifies dependency reachability, not fuzz quality.

A reachable fuzzer can still have weak input diversity or an inadequate oracle.

## Sanitizer relationship

The repository has a `host-sanitize` target using AddressSanitizer and UndefinedBehaviorSanitizer for selected host tests.

At the reviewed revision, the dedicated fuzz targets are compiled by their normal make rules without ASan/UBSan instrumentation.

This is an obvious improvement opportunity.

Fuzzing becomes much more valuable when memory/undefined-behavior sanitizers can turn silent corruption into an immediate reproducible failure.

## Fuzzer oracle design

A fuzzer is only as strong as its oracle.

Current useful ChrisOS fuzz oracles include:

- return code stays inside defined domain;
- no resource leak after rejection;
- current process restored;
- filesystem fsck remains clean;
- valid control input still succeeds;
- parser error message exists;
- decoded instruction length remains bounded;
- live-resource count returns to baseline.

"Did not crash" alone is a weak oracle.

The project already has several semantic invariants that should be expanded.

## Seed management

Fixed seeds make CI stable but limit exploration.

A future model should use two modes.

### CI mode

Use a fixed set of published seeds.

This guarantees deterministic regression behavior.

### Exploration mode

Generate or accept many seeds over longer runs.

Every failure must print:

- seed;
- target;
- iteration;
- input length;
- exact input artifact;
- revision.

The first failing input should then be minimized and added to the deterministic regression corpus.

## Corpus management

ChrisOS does not currently maintain a dedicated fuzz corpus directory for these targets.

A future layout could separate targets:

    fuzz/corpus/elf/
    fuzz/corpus/clvm/
    fuzz/corpus/chrisc/
    fuzz/corpus/cfs/
    fuzz/corpus/chrisvm-decode/
    fuzz/corpus/shader/

Every fixed bug should contribute at least one minimal reproducer.

This converts previously discovered bugs into permanent regression coverage.

## Coverage-guided fuzzing

Coverage-guided fuzzing selects future mutations based on whether an input reaches new control-flow edges.

Conceptually:

[
score(x) propto new_coverage(x)
]

This is different from the current fixed random stream.

Useful future host integrations include compiler instrumentation compatible with libFuzzer or AFL-family tooling.

The production code under test should remain the same implementation where possible; only the host harness and instrumentation should differ.

## Grammar-aware fuzzing

Some ChrisOS formats have enough structure that pure byte mutation is inefficient.

High-value structured generators include:

- ELF program-header layouts;
- CLVM headers/sections/opcodes;
- ChrisC token/AST grammar;
- shader grammar and CSI serialization;
- ChrisFS path trees and operation sequences;
- ChrisVM instruction prefixes/opcodes/addressing modes.

A grammar-aware generator can create mostly valid outer structure while mutating semantic boundaries deeper inside the parser.

## Stateful fuzzing

ChrisFS is inherently stateful.

The input is not one buffer; it is an operation sequence:

[
S = (op_1, op_2, ldots, op_n)
]

where operations include create, write, rename, unlink, mkdir, read, remount and fsck.

The existing CFS test already approximates this idea.

A stronger stateful fuzzer should preserve the sequence that produced failure and minimize the operation list.

## Differential testing

Where another implementation or model exists, differential testing can provide a powerful oracle.

Potential future examples:

- ChrisVM decoder versus a trusted disassembler for supported instruction subsets;
- native/interpreter/JIT results for the same CLVM/ChrisC program;
- shader software execution versus selected reference calculations;
- ChrisFS model state versus on-disk state.

Differential testing does not prove both implementations correct, but disagreements reveal high-value cases.

## Time budget and scaling

Fuzzing can consume unbounded time.

The test hierarchy should separate:

- fast deterministic smoke fuzzing for every commit;
- sanitizer fuzzing for CI/nightly runs;
- long exploration campaigns outside the normal build;
- minimized regression cases committed permanently.

The current dedicated tests are appropriately small for normal gate execution.

Long campaigns should not make ordinary development feedback impractical.

## Security relevance

Fuzzing is especially relevant to ChrisOS security boundaries that parse attacker-controlled or malformed data.

Current high-value areas include:

- ELF loading;
- compiler/VM images;
- filesystem names and metadata;
- shader input;
- future network packet parsers.

A fuzz-found crash should be classified by reachability and privilege boundary rather than automatically called a security vulnerability.

## Current coverage summary

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`:

- ChrisFS: 200 deterministic random operation/path cases followed by fsck;
- ELF: 300 random byte inputs with periodic ELF magic and allocation-pressure cleanup checks;
- ChrisC: 48 random printable-source cases plus valid-control compilation;
- CLVM: 200 random image buffers plus valid round-trip control;
- ChrisVM decoder: 2000 deterministic random byte sequences in the ChrisVM test suite;
- shader/CSI: structured malformed and mutation cases in the shader host suite;
- dedicated CFS/ELF/ChrisC/CLVM fuzz targets participate in `host-gates` and `host-stress`.

This is meaningful adversarial regression coverage, but not yet coverage-guided fuzzing.

## Highest-value next steps

The next improvements should be:

1. run dedicated fuzz targets under ASan/UBSan;
2. add a reproducible multi-seed mode;
3. persist failing inputs automatically;
4. minimize failures and commit regression corpus entries;
5. add coverage instrumentation;
6. add grammar-aware ChrisC/CLVM/ELF mutation;
7. expand ChrisFS into a stateful operation-sequence fuzzer;
8. fuzz ChrisVM execution after successful decode;
9. add parser-specific invariants, not only crash detection;
10. publish fuzz duration, executions and coverage metrics in CI artifacts.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The repository already runs deterministic adversarial input tests in ordinary validation. The next maturity step is to preserve that reproducibility while adding sanitizer instrumentation, corpus management, coverage feedback and automatic minimization.
