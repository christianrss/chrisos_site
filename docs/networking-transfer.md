---
title: "22 Networking & transfer"
description: "VirtIO networking, guest-host file transfer and the protocols used to move data into a running ChrisOS environment."
---

<div class="retro-kicker">HARDWARE & APPLICATIONS · 22</div>

# Networking & transfer

<div class="lang-switch"><a href="../pt-br/networking-transfer/">Português</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Source edition:** `main @ da3df29` · documentation migrated to GitHub Pages

VirtIO networking, guest-host file transfer and the protocols used to move data into a running ChrisOS environment.

## What this page should answer

This route preserves the editorial architecture of the original documentation. Content should be updated from code and tests on `main`, never from stale prose alone.

<div class="retro-panel">
<strong>Code map</strong><br>
<code>README.md · docs/ · relevant source and tests on main</code>
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

[23 Desktop & applications](./desktop-applications.md)
