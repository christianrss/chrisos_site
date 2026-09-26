---
title: "16 Gráficos 2D e composição"
description: "O caminho de desenho por software, backbuffer, compositor, surfaces de aplicações e a API estável independente da GPU."
---

<div class="retro-kicker">GRÁFICOS E INTERAÇÃO · 16</div>

# Gráficos 2D e composição

<div class="lang-switch"><a href="../../graphics-2d/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

O caminho de desenho por software, backbuffer, compositor, surfaces de aplicações e a API estável independente da GPU.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>kernel/gfx/graphics.c · kernel/gfx/gfx2d.c · kernel/wm/</code>
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

[17 3D por software](./software-3d.md)
