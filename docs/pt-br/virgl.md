---
title: "19 Transporte 3D VirGL"
description: "O transporte 3D acelerado sobre VirtIO-GPU, objetos reutilizáveis do renderer e a diferença entre transporte e semântica da API."
---

<div class="retro-kicker">GRÁFICOS E INTERAÇÃO · 19</div>

# Transporte 3D VirGL

<div class="lang-switch"><a href="../../virgl/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

O transporte 3D acelerado sobre VirtIO-GPU, objetos reutilizáveis do renderer e a diferença entre transporte e semântica da API.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>kernel/gfx/ · reusable VirGL backend and host/QEMU gates</code>
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

[20 Subset GLSL e CSIR](./glsl-csir.md)
