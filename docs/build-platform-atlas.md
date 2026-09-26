---
title: "37 Build & platform atlas"
description: "A map of make targets, linker configuration, boot staging, images and architecture-specific build paths."
---

<div class="retro-kicker">REFERENCE · 37</div>

# Build & platform atlas

<div class="lang-switch"><a href="../pt-br/build-platform-atlas/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

A map of make targets, linker configuration, boot staging, images and architecture-specific build paths.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>makefile · linker.ld · third_party/limine</code>
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

[Back to the beginning](./inside-chrisos.md)
