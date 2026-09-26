---
title: "26 RISC-V bring-up"
description: "The secondary architecture bring-up, what it proves about portability and where x86-64 assumptions still leak through."
---

<div class="retro-kicker">HARDWARE & APPLICATIONS · 26</div>

# RISC-V bring-up

<div class="lang-switch"><a href="../pt-br/riscv/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

The secondary architecture bring-up, what it proves about portability and where x86-64 assumptions still leak through.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>RISC-V build targets and architecture-specific kernel path</code>
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

[27 ChrisVM roadmap](./chrisvm.md)
