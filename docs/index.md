---
title: ChrisOS
description: Official ChrisOS ecosystem documentation.
---

<div class="hero-retro">
  <div class="hero-system">CHRISOS / DOCUMENTATION / 2026</div>
  <img src="assets/images/ChrisOS_Monolito.png" class="hero-logo" alt="ChrisOS Monolith logo">
  <div class="hero-eyebrow">THE CHRISOS ECOSYSTEM</div>
  <h1>Inside ChrisOS</h1>
  <p>An operating system, a language, and the tools to build both. From the first instruction to the desktop.</p>
  <div class="hero-actions">
    <a class="retro-button primary" href="inside-chrisos/">ENTER DOCUMENTATION</a>
    <a class="retro-button" href="pt-br/">PT-BR</a>
    <a class="retro-button" href="https://github.com/christianrss/ChrisOS" target="_blank">SOURCE ↗</a>
  </div>
  <div class="hero-status"><span class="led"></span> SOURCE EDITION: main @ da3df29 · 26 SEP 2026</div>
</div>

## System map

<div class="ascii-map">

```text
                         ChrisOS
                            │
           ┌────────────────┼────────────────┐
           │                │                │
        Kernel           ChrisC           ChrisFS
           │                │                │
   metal / drivers     compiler + CLVM    persistence
           │                │                │
           ├──── graphics ──┼──── apps ──────┤
           │                │                │
      VirtIO / VirGL       JIT          Desktop / Tools
           │
       real hardware
```

</div>

## Reading paths

| Goal | Start | Continue |
|---|---|---|
| Run the project | [Build & run](build-run/) | Boot → desktop → validation |
| Understand the OS | [System architecture](system-architecture/) | Memory → interrupts → processes → ChrisFS |
| Write programs | [ChrisC](chrisc-language/) | CLVM → libraries → IDE → native toolchain |
| Understand the GPU | [2D graphics](graphics-2d/) | Software 3D → VirtIO-GPU → VirGL → shaders |
| Follow self-hosting | [Self-hosting](self-hosting/) | Native toolchain → installation → roadmap |

## Current source baseline

This GitHub Pages edition tracks the ChrisOS `main` branch. The current migration baseline is commit `da3df29`, replacing the earlier Sites snapshot that was tied to `feat/os2 @ 252b92e`.

<div class="status-grid">
  <div><b>KERNEL</b><span>x86-64 higher-half, memory, interrupts, processes</span></div>
  <div><b>LANGUAGE</b><span>ChrisC + CLVM + JIT + native toolchain work</span></div>
  <div><b>GRAPHICS</b><span>software path + VirtIO-GPU + reusable VirGL backend</span></div>
  <div><b>STORAGE</b><span>ChrisFS and multiple block-device paths</span></div>
</div>
