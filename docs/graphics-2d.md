---
title: "16 2D graphics & composition"
description: "The software drawing path, backbuffer, compositor, application surfaces and the stable API that must remain independent of GPU hardware."
---

<div class="retro-kicker">GRAPHICS & INTERACTION · 16</div>

# 2D graphics & composition

<div class="lang-switch"><a href="../pt-br/graphics-2d/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

The software drawing path, backbuffer, compositor, application surfaces and the stable API that must remain independent of GPU hardware.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>kernel/gfx/graphics.c · kernel/gfx/gfx2d.c · kernel/wm/</code>
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

[17 Software 3D](./software-3d.md)
