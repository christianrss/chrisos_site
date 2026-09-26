---
title: "18 VirtIO-GPU"
description: "Virtqueues, recursos, backing memory, scanout, cursor e ciclo de vida dos recursos do dispositivo gráfico paravirtual."
---

<div class="retro-kicker">GRÁFICOS E INTERAÇÃO · 18</div>

# VirtIO-GPU

<div class="lang-switch"><a href="../../virtio-gpu/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Virtqueues, recursos, backing memory, scanout, cursor e ciclo de vida dos recursos do dispositivo gráfico paravirtual.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>kernel/gfx/ · VirtIO-GPU resource and scanout code</code>
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

[19 Transporte 3D VirGL](./virgl.md)
