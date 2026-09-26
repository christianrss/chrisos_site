---
title: "34 Applications & libraries atlas"
description: "A map of first-party applications and libraries, emphasizing which kernel/runtime contracts each one exercises."
---

<div class="retro-kicker">REFERENCE · 34</div>

# Applications & libraries atlas

<div class="lang-switch"><a href="../pt-br/apps-libraries-atlas/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

A map of first-party applications and libraries, emphasizing which kernel/runtime contracts each one exercises.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>APPS/ · LIB/</code>
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

[35 Game source atlas](./games-atlas.md)
