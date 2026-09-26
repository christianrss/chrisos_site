---
title: "19 VirGL 3D transport"
description: "The accelerated 3D transport layered over VirtIO-GPU, reusable renderer objects and the distinction between transport and API semantics."
---

<div class="retro-kicker">GRAPHICS & INTERACTION · 19</div>

# VirGL 3D transport

<div class="lang-switch"><a href="../pt-br/virgl/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

The accelerated 3D transport layered over VirtIO-GPU, reusable renderer objects and the distinction between transport and API semantics.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>kernel/gfx/ · reusable VirGL backend and host/QEMU gates</code>
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

[20 GLSL subset & CSIR](./glsl-csir.md)
