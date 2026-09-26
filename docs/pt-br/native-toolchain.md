---
title: "12 KCC, ChrisAsm e ChrisLd"
description: "O caminho do toolchain nativo para produzir objetos, linkar executáveis e futuramente reconstruir o sistema internamente."
---

<div class="retro-kicker">LINGUAGENS E FERRAMENTAS · 12</div>

# KCC, ChrisAsm e ChrisLd

<div class="lang-switch"><a href="../../native-toolchain/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

O caminho do toolchain nativo para produzir objetos, linkar executáveis e futuramente reconstruir o sistema internamente.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>compiler/kcc/ · compiler/chrisasm/ · compiler/chrisld/</code>
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

[13 Editor, debugger e build](./editor-debugger-build.md)
