---
id: reproducible-builds
lang: en
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - kernel/metal/buildid.c
  - kernel/metal/buildid.h
  - tools/buildstamp.c
  - tools/stamp_kernel.c
  - tools/test_buildstamp.c
  - tools/test_buildinfo.c
  - tools/cfs_mkdisk.c
  - kernel/fs/cfs.c
  - scripts/check-dev-env.sh
  - tests/cc-fixed.sh
  - .cursor/install.sh
symbols:
  - build_git
  - build_id
  - build_date
  - build_compiler
  - build_kernel_sha256
  - buildstamp_seal
  - cfs_set_now
depends_on:
  - stage-compilers
  - internal-kernel-build
related:
  - selfhost-levels
  - validation-evidence
---

# Reproducible builds and provenance

## Scope

A reproducible build is not the same thing as a successful build, a self-hosted build, or a build with a checksum.

For ChrisOS, reproducibility must be discussed per artifact:

- kernel ELF;
- bootable ISO;
- ChrisFS disk image;
- compiler stages;
- generated application binaries.

The current repository already contains useful provenance mechanisms, especially Git-derived build metadata and a stamped kernel hash. It also contains at least one real fixed-point compiler test.

However, the current x86-64 kernel and ISO build are not configured for byte-for-byte reproducibility across independent build times and host environments.

The main blockers are explicit and inspectable.

## Reproducibility versus provenance

Reproducibility asks:

> Given the declared same inputs, can independent builds produce equivalent output?

Provenance asks:

> Which source revision, toolchain, dependencies, and build conditions produced this artifact?

Integrity asks:

> Has this specific artifact changed since it was produced?

These are separate properties.

ChrisOS already has a useful integrity mechanism for the kernel, but its provenance record is incomplete and its default build intentionally embeds time-dependent metadata.

## Kernel source revision

The makefile defines:

```text
CHRIS_GIT := git rev-parse --short=12 HEAD
```

and passes that value into the kernel as:

```text
CHRIS_GIT
```

This gives the running kernel a compact source revision identifier.

It is useful, but it is not a complete source-state identity.

## Short SHA limitation

Only twelve hexadecimal characters of HEAD are embedded.

That is normally enough for convenient repository identification, but it is weaker than storing the full commit hash in a provenance record.

A reproducibility manifest should preserve the full revision.

The short identifier can remain in human-readable UI.

## Dirty-tree limitation

The build ID does not record whether the Git working tree contains local modifications.

`git rev-parse HEAD` identifies the committed parent state, not the actual bytes of every source file used by the compiler.

Therefore two builds can report the same Git revision while one was produced from modified uncommitted sources.

The stamped kernel hash will distinguish different resulting binaries, but it cannot explain which source modifications caused the difference.

A strong provenance gate must either reject dirty trees or hash the effective source inputs.

## Build time is embedded

The makefile defines:

```text
CHRIS_DATE := date -u +%Y-%m-%dT%H:%M:%SZ
```

and:

```text
CHRIS_BUILD_ID = CHRIS_GIT-CHRIS_DATE
```

Both the date and build ID are compiled into the kernel.

Consequently, two clean builds of the same commit at different UTC seconds have different source-level macro values and therefore different kernel bytes.

This alone prevents default byte-for-byte kernel reproducibility.

## No SOURCE_DATE_EPOCH policy

The repository does not currently use:

```text
SOURCE_DATE_EPOCH
```

or an equivalent normalized timestamp input for the kernel build.

A reproducible mode should derive all build timestamps from a declared deterministic value, typically the source commit timestamp or an explicit environment variable.

Wall-clock time can still be shown separately as build-environment metadata, but it should not alter the artifact when deterministic mode is requested.

## Runtime build information

`buildid.c` exposes:

- Git revision;
- build ID;
- build date;
- compiler version;
- kernel SHA-256 stamp.

`build_info_format` formats these fields for runtime inspection.

This is useful provenance visibility.

It also means compiler identity is embedded into the binary through `__VERSION__`, so compiler-version changes may change kernel bytes even when code generation happened to be otherwise equivalent.

## Toolchain version coverage

The development environment requires:

- GCC;
- GNU ld/binutils;
- NASM;
- xorriso;
- Python;
- Git.

The environment checker validates availability, not exact hermetic versions.

The build info exposes the compiler's `__VERSION__`, but it does not record:

- GNU ld version;
- NASM version;
- xorriso version;
- Python version.

Different tool releases may legally emit different bytes from the same source and flags.

Thus a reproducibility report needs a complete toolchain fingerprint.

## Cloud bootstrap compiler choice

The cloud install script intentionally selects GCC 11 when available because the project documents a warning/error interaction with newer GCC versions.

This is already evidence that compiler version materially matters to the build.

However, package installation by distribution package name is not the same as hermetically pinning the compiler binary.

A stronger setup would record hashes or container/image identities for the complete build toolchain.

## Pinned third-party source

The cloud bootstrap script contains explicit commit hashes for dependencies such as Limine and doomgeneric.

This is good provenance practice.

For example, Limine is associated with a specific commit SHA rather than only a moving branch name.

## Existing dependency verification gap

The bootstrap script only fetches those pinned dependencies when the expected path is absent.

If the directory already exists, it reports that it is present rather than verifying that the checkout still matches the declared commit hash.

Therefore the pin documents intended provenance but does not fully enforce it on an already-populated working tree.

A reproducible-build gate should verify dependency revisions every time.

## Kernel stamp mechanism

After GNU ld produces the kernel, the build invokes:

```text
stamp_kernel
```

The kernel contains a marker:

```text
CHRISOSHASH:
```

followed by 64 hexadecimal zero characters.

`buildstamp_seal` finds that slot, zeroes its 64 characters, calculates SHA-256 over the complete image in that zeroed state, and writes the hexadecimal digest back into the slot.

## What the stamp proves

The stamp creates a deterministic identity for the linked image before the digest field is filled.

At runtime:

```text
build_kernel_sha256()
```

returns that embedded digest.

This lets logs and panic reports identify the exact stamped kernel artifact.

It is a strong artifact-identity mechanism.

## Stamp semantics are not the final-file SHA-256

The embedded value is not simply:

```text
sha256sum final-kernel.elf
```

because the hash is computed while the digest field contains zeros.

After the digest is written into the ELF, the final file bytes have changed.

Therefore external verification must reproduce the "zero the hash slot, then hash" algorithm, or the project must additionally publish a conventional hash of the final file.

This distinction should be explicit in provenance tooling.

## Stamp tests

`tools/test_buildstamp.c` verifies that:

- the correct digest is written;
- bytes outside the identity slot are unchanged;
- images without the marker are rejected.

`tools/test_buildinfo.c` verifies the formatted build fields and the 64-character kernel identity width.

These tests validate the provenance mechanism itself.

They do not test that two independent kernel builds produce identical outputs.

## Missing kernel reproducibility gate

The repository currently has no equivalent of:

```text
clean build A
clean build B
compare kernel A and kernel B
```

There is no dedicated `SOURCE_DATE_EPOCH` build mode and no checked gate using `cmp`, a conventional SHA-256 pair, or a binary-difference tool for two independently produced kernel images.

Therefore byte reproducibility of the kernel is not currently established.

## Existing fixed-point precedent

The repository does contain an important convergence test:

```text
tests/cc-fixed.sh
```

It bootstraps the ChrisC application compiler through stages:

```text
CC1.CLV
CC2.CLV
CC3.CLV
```

and executes:

```text
cmp build/CC2.CLV build/CC3.CLV
```

This is real byte-for-byte fixed-point evidence for that specific compiler path.

It is not evidence for KCC or the kernel, but it provides a useful pattern for future stage and reproducibility gates.

## Kernel gate modeled after the fixed-point test

A kernel reproducibility test can follow the same philosophy:

1. start from one exact clean source state;
2. use one declared toolchain;
3. set a normalized build timestamp;
4. build kernel A;
5. clean all derived kernel outputs;
6. rebuild kernel B;
7. compare conventional final-file hashes;
8. if unequal, preserve both artifacts and a machine-readable difference report.

A second CI environment can then repeat the test to distinguish same-host determinism from cross-environment reproducibility.

## ISO reproducibility

The ISO is produced by xorriso and then modified by:

```text
limine bios-install
```

The current xorriso invocation does not define a repository-level normalized timestamp policy such as `SOURCE_DATE_EPOCH` handling or explicit normalized ISO date fields.

The repository therefore does not establish that two ISO builds are byte-identical even after the kernel itself becomes deterministic.

ISO reproducibility must be tested separately from kernel reproducibility.

## ISO input tree

The ISO staging tree contains:

- kernel ELF;
- Limine configuration;
- Limine BIOS files;
- Limine UEFI image.

Reproducibility requires both deterministic contents and deterministic filesystem metadata/layout generated by the ISO toolchain.

A kernel hash match does not imply an ISO hash match.

## Limine post-processing

`limine bios-install` mutates the ISO after xorriso writes it.

That operation is part of the artifact pipeline and must be included in the reproducibility boundary.

The final ISO hash should always be taken after Limine installation.

Tool version and pinned Limine revision are therefore part of ISO provenance.

## ChrisFS disk image

`cfs_mkdisk` starts from a zero-sized/zero-filled fixed-size file and formats a new CFS image.

CFS does not automatically use host wall-clock time for its normal metadata clock.

The global CFS clock starts at:

```text
1
```

and inode stamping increments that logical value unless `cfs_set_now` is explicitly given another value.

This removes one common wall-clock source of nondeterminism from a fresh formatter process.

## Persistent disk behavior

The normal Make target does not rebuild `build/disk.img` when it already exists.

It prints that the image exists and tells the developer to remove it to recreate it.

Many application, smoke-test, and seed targets then mutate that persistent image by copying files into it.

Therefore `disk.img` is normally a workspace state artifact, not a reproducible build artifact.

Its bytes can encode previous development activity.

## Two disk-image classes

Documentation should distinguish:

```text
workspace disk
release/reference disk
```

The workspace disk is intentionally persistent and mutable.

A reproducible reference disk should always start from a newly created zeroed image and receive files in a fixed declared order from a fixed manifest.

Those two use cases should not share the same reproducibility claim.

## Source-order and object-order determinism

The kernel object list in the makefile has an explicit order, and GNU ld receives objects in that order.

This is a useful deterministic input property.

However, fixed link order does not solve:

- variable build date;
- dirty source state;
- compiler/binutils version drift;
- generated-input drift;
- third-party checkout drift.

Reproducibility is an end-to-end property.

## Reproducibility levels for ChrisOS

A useful classification is:

```text
R0  artifact has an integrity hash
R1  same machine/toolchain rebuild is byte-identical
R2  clean independent environment with pinned tools is byte-identical
R3  independently provisioned builders reproduce published artifact
R4  self-hosted/staged compiler chain also converges
```

Current kernel support is strongest at R0.

The ChrisC fixed-point test demonstrates a specialized R1/R4-like property for that compiler artifact, not for the kernel.

## Required provenance manifest

A release-quality manifest should include:

- full Git commit;
- dirty-tree state or source-tree hash;
- normalized build timestamp;
- GCC version and binary hash;
- GNU ld version;
- NASM version;
- xorriso version;
- Python version;
- Limine commit;
- other third-party commits;
- build flags;
- generated-input hashes;
- kernel final-file SHA-256;
- embedded zero-slot kernel stamp;
- ISO final SHA-256;
- reference-disk SHA-256 when applicable.

This allows a mismatch to be explained instead of merely detected.

## Immediate engineering path

The shortest path to reproducible kernel builds is:

1. add a deterministic-build mode;
2. replace wall-clock `CHRIS_DATE` with a normalized input in that mode;
3. record the full Git SHA and reject or explicitly record dirty trees;
4. pin and verify the complete host toolchain;
5. verify third-party checkouts even when already present;
6. run two clean kernel builds and compare them;
7. preserve conventional final-file hashes in addition to the embedded stamp;
8. create a separate ISO reproducibility gate;
9. create a fresh reference-disk manifest/gate;
10. extend the same approach to KCC1/KCC2 stage convergence.

## Revision note

This chapter was written against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. ChrisOS already has strong artifact identity for the kernel and a real byte-level fixed-point test for the ChrisC application compiler. The default kernel build is not byte-reproducible across build times because it embeds the current UTC time, and complete cross-environment provenance is not yet pinned or verified.
