---
title: "36 Tests & tools atlas"
description: "A map of host tests, QEMU gates, generators, transfer utilities and validation tooling."
---

<div class="retro-kicker">REFERENCE · 36</div>

# Tests & tools atlas

<div class="lang-switch"><a href="../pt-br/tests-tools-atlas/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

A map of host tests, QEMU gates, generators, transfer utilities and validation tooling.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>tools/ · tests / make gates</code>
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

[37 Build & platform atlas](./build-platform-atlas.md)
