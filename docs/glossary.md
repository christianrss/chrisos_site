---
title: "30 Technical glossary"
description: "A common vocabulary for ABI, HHDM, PMM, TLB, DMA, MMIO, VirtIO, CLVM, CSIR and the other terms used throughout the project."
---

<div class="retro-kicker">REFERENCE · 30</div>

# Technical glossary

<div class="lang-switch"><a href="../pt-br/glossary/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

A common vocabulary for ABI, HHDM, PMM, TLB, DMA, MMIO, VirtIO, CLVM, CSIR and the other terms used throughout the project.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>README.md · docs/ · relevant source and tests on main</code>
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

[31 Maintain this documentation](./maintain-docs.md)
