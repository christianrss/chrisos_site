---
title: "08 ChrisFS & persistence"
description: "Persistent workspace design, block-device abstraction, ChrisFS layout, compatibility and install-media implications."
---

<div class="retro-kicker">SYSTEM FOUNDATIONS · 08</div>

# ChrisFS & persistence

<div class="lang-switch"><a href="../pt-br/chrisfs-persistence/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

Persistent workspace design, block-device abstraction, ChrisFS layout, compatibility and install-media implications.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>kernel/fs/cfs.c · kernel/fs/cfs_format.h · block_device.h</code>
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

[09 ChrisC language](./chrisc-language.md)
