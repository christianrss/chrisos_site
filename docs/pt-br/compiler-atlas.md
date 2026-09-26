---
title: "33 Atlas do compilador"
description: "Mapa de leitura para ChrisC, CLVM, JIT, debugger e o toolchain nativo KCC/ChrisAsm/ChrisO/ChrisLd."
---

<div class="retro-kicker">REFERÊNCIA · 33</div>

# Atlas do compilador

<div class="lang-switch"><a href="../../compiler-atlas/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Mapa de leitura para ChrisC, CLVM, JIT, debugger e o toolchain nativo KCC/ChrisAsm/ChrisO/ChrisLd.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>compiler/</code>
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

[34 Atlas de aplicações e bibliotecas](./apps-libraries-atlas.md)
