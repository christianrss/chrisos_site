---
title: "18 VirtIO-GPU"
description: "Virtqueues, resources, backing memory, scanout, cursor handling and the resource lifecycle of the paravirtual display device."
---

<div class="retro-kicker">GRAPHICS & INTERACTION · 18</div>

# VirtIO-GPU

<div class="lang-switch"><a href="../pt-br/virtio-gpu/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

Virtqueues, resources, backing memory, scanout, cursor handling and the resource lifecycle of the paravirtual display device.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>kernel/gfx/ · VirtIO-GPU resource and scanout code</code>
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

[19 VirGL 3D transport](./virgl.md)
