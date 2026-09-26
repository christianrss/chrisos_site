---
title: "07 Processes & system calls"
description: "Native execution boundaries, process address spaces, system calls and the separate CLVM execution contract."
---

<div class="retro-kicker">SYSTEM FOUNDATIONS · 07</div>

# Processes & system calls

<div class="lang-switch"><a href="../pt-br/processes-syscalls/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

Native execution boundaries, process address spaces, system calls and the separate CLVM execution contract.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>kernel/metal/proc.c · kernel/metal/syscall.c · kernel/metal/elf.c</code>
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

[08 ChrisFS & persistence](./chrisfs-persistence.md)
