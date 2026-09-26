---
title: "05 Memory & ownership"
description: "PMM, virtual memory, heap allocation, ownership rules and why lifecycle discipline matters across kernel subsystems."
---

<div class="retro-kicker">SYSTEM FOUNDATIONS · 05</div>

# Memory & ownership

<div class="lang-switch"><a href="../pt-br/memory-ownership/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

PMM, virtual memory, heap allocation, ownership rules and why lifecycle discipline matters across kernel subsystems.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>kernel/metal/pmm.c · kernel/metal/mm.c · heap / ownership audits</code>
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

[06 Interrupts & SMP](./interrupts-smp.md)
