---
title: "12 KCC, ChrisAsm & ChrisLd"
description: "The native toolchain path toward producing objects, linking executables and eventually rebuilding the operating system internally."
---

<div class="retro-kicker">LANGUAGES & TOOLS · 12</div>

# KCC, ChrisAsm & ChrisLd

<div class="lang-switch"><a href="../pt-br/native-toolchain/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

The native toolchain path toward producing objects, linking executables and eventually rebuilding the operating system internally.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>compiler/kcc/ · compiler/chrisasm/ · compiler/chrisld/</code>
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

[13 Editor, debugger & build](./editor-debugger-build.md)
