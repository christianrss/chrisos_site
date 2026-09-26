---
title: "11 JIT e caminhos de execução"
description: "Interpretador, JIT nativo e como a execução transita entre semântica de bytecode e código de máquina x86-64."
---

<div class="retro-kicker">LINGUAGENS E FERRAMENTAS · 11</div>

# JIT e caminhos de execução

<div class="lang-switch"><a href="../../jit-execution/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Interpretador, JIT nativo e como a execução transita entre semântica de bytecode e código de máquina x86-64.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>compiler/jit/</code>
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

[12 KCC, ChrisAsm e ChrisLd](./native-toolchain.md)
