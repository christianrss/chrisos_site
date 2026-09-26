---
title: "17 3D por software"
description: "Transformações na CPU, rasterização, depth e o renderer de referência usado para provar comportamento sem aceleração de GPU."
---

<div class="retro-kicker">GRÁFICOS E INTERAÇÃO · 17</div>

# 3D por software

<div class="lang-switch"><a href="../../software-3d/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Transformações na CPU, rasterização, depth e o renderer de referência usado para provar comportamento sem aceleração de GPU.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>kernel/gfx/math3d.c · kernel/gfx/tri.c · kernel/gfx/voxel.c</code>
</div>

## Modelo de evidência

| Rótulo | Significado |
|---|---|
| **Implemented** | Existe implementação rastreável no código. |
| **Host-tested** | Há teste reproduzível executado fora do guest. |
| **QEMU-proven** | Há gate que prova o comportamento no perfil emulado declarado. |
| **Hardware-proven** | Há evidência em máquina física identificada. |

!!! note "Regra editorial"
    Roadmap, intenção arquitetural e implementação observada são categorias diferentes. Quando houver divergência, registre a revisão e a evidência.

## Próxima leitura

[18 VirtIO-GPU](./virtio-gpu.md)
