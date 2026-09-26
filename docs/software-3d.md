---
title: "17 Software 3D"
description: "CPU-side transforms, rasterization, depth and the reference rendering path used to prove graphics behavior without GPU acceleration."
---

<div class="retro-kicker">GRAPHICS & INTERACTION · 17</div>

# Software 3D

<div class="lang-switch"><a href="../pt-br/software-3d/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

CPU-side transforms, rasterization, depth and the reference rendering path used to prove graphics behavior without GPU acceleration.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>kernel/gfx/math3d.c · kernel/gfx/tri.c · kernel/gfx/voxel.c</code>
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

[18 VirtIO-GPU](./virtio-gpu.md)
