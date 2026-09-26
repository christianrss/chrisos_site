---
title: "11 JIT & execution paths"
description: "Interpreter, native JIT and how execution can move between bytecode semantics and x86-64 machine code."
---

<div class="retro-kicker">LANGUAGES & TOOLS · 11</div>

# JIT & execution paths

<div class="lang-switch"><a href="../pt-br/jit-execution/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

Interpreter, native JIT and how execution can move between bytecode semantics and x86-64 machine code.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>compiler/jit/</code>
</div>

## Evidence model

| Label | Meaning |
|---|---|
| **Implemented** | Traceable implementation exists in source. |
| **Host-tested** | A reproducible test runs outside the guest. |
| **QEMU-proven** | A gate proves behavior under the declared emulated profile. |
| **Hardware-proven** | There is evidence on an identified physical machine. |

!!! note "Editorial rule"
    Roadmap, architectural intent and observed implementation are different categories. When they diverge, record the revision and the evidence.

## Next reading

[12 KCC, ChrisAsm & ChrisLd](./native-toolchain.md)
