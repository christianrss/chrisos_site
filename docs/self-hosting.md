---
title: "14 Self-hosting"
description: "What self-hosting means for ChrisOS, which bootstrap stages exist, and which proofs are required before a stage can be called closed."
---

<div class="retro-kicker">LANGUAGES & TOOLS · 14</div>

# Self-hosting

<div class="lang-switch"><a href="../pt-br/self-hosting/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

What self-hosting means for ChrisOS, which bootstrap stages exist, and which proofs are required before a stage can be called closed.

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

[15 Libraries, modules & GC](./libraries-modules-gc.md)
