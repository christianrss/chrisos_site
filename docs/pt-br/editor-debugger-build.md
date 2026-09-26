---
title: "13 Editor, debugger e build"
description: "ChrisEditor, sessões de depuração, mapas de fonte e o tooling necessário para desenvolver produtivamente dentro do ChrisOS."
---

<div class="retro-kicker">LINGUAGENS E FERRAMENTAS · 13</div>

# Editor, debugger e build

<div class="lang-switch"><a href="../../editor-debugger-build/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

ChrisEditor, sessões de depuração, mapas de fonte e o tooling necessário para desenvolver produtivamente dentro do ChrisOS.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>APPS/EDITOR/ · compiler/debug/</code>
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

[14 Self-hosting](./self-hosting.md)
