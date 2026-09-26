---
title: "02 Arquitetura do sistema"
description: "As fronteiras entre boot, kernel, runtime, aplicações, filesystem, gráficos e ferramentas de desenvolvimento."
---

<div class="retro-kicker">COMECE AQUI · 02</div>

# Arquitetura do sistema

<div class="lang-switch"><a href="../../system-architecture/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

As fronteiras entre boot, kernel, runtime, aplicações, filesystem, gráficos e ferramentas de desenvolvimento.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>README.md · docs/ · relevant source and tests on main</code>
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

[03 Mapa do repositório](./repository-map.md)
